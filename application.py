import os
import flask
import requests
import pydantic
from hashlib import md5
from flask import jsonify
from flask import request as fk_request
from flask.views import MethodView
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# подключение flask + DB
application = flask.Flask('application')
# немного магии с кодировкой
application.config['JSON_AS_ASCII'] = False
PG_DSN = f"postgres://castom:castom@127.0.0.1:5432/advertisement"
engine = create_engine(PG_DSN)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class HttpErrors(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


# обработчик ошибок
@application.errorhandler(HttpErrors)
def http_err_handle(error):
    response = flask.jsonify({'message': error.message})
    response.status_code = error.status_code
    return response


class UserModel(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_name = Column(String(120), nullable=False, unique=True)
    email = Column(String(120), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    reg_time = Column(DateTime, server_default=func.now())
    is_authorized = Column(Boolean, unique=False, default=False)
    adv = relationship('AdvertisementModel')


class UserValidator(pydantic.BaseModel):
    user_name: str
    password: str
    email: str

    @pydantic.validator('password')
    def strong_pass(cls, value):
        if len(value) < 9:
            raise ValueError('password length must be more than 9 characters')
        return value

    @pydantic.validator('user_name')
    def user_exist(cls, value):
        current_session = Session()
        input_data = dict(fk_request.json)
        user_data = current_session.query(UserModel).filter(UserModel.user_name == input_data['user_name']).first()
        if user_data:
            raise HttpErrors(400, f"a user with the same name ({input_data['user_name']}) already exists")
        return value

    @pydantic.validator('email')
    def email_exist(cls, value):
        current_session = Session()
        input_data = dict(fk_request.json)
        user_data = current_session.query(UserModel).filter(UserModel.email == input_data['email']).first()
        if user_data:
            raise HttpErrors(400, f"a user with the same email ({input_data['email']}) already exists")
        return value


class AdvertisementModel(Base):
    __tablename__ = 'advertisement'
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    description = Column(String(250), nullable=False)
    create_time = Column(DateTime, server_default=func.now())
    owner = Column(Integer, ForeignKey('users.id'))


class AdvertisementValidate(pydantic.BaseModel):
    title: str
    description: str
    owner: int

    @pydantic.validator('owner')
    def user_is_authorized(cls, value):
        current_session = Session()
        input_data = dict(fk_request.json)
        user_data = current_session.query(UserModel).filter(UserModel.id == input_data['owner']).first()

        if user_data.is_authorized == False:
            raise HttpErrors(400, f" user ({user_data.user_name}) not authorized!")
        return value


# проверка миграций
Base.metadata.create_all(engine)


class UserView(MethodView):
    def get(self):
        current_session = Session()
        users_data = current_session.query(UserModel).all()
        result = dict()
        for user in users_data:
            result[user.id] = {
                "id": user.id,
                "user_name": user.user_name,
                "is_authorized": user.is_authorized
            }

        return flask.jsonify(result)

    def post(self):
        # валидация
        try:
            input_data = UserValidator(**fk_request.json).dict()
        except pydantic.ValidationError as err:
            raise HttpErrors(400, err.errors())

        # хешируем пароль
        input_data['password'] = str(md5(input_data['password'].encode()).hexdigest())

        new_user = UserModel(**input_data)
        current_session = Session()

        current_session.add(new_user)
        current_session.commit()

        return flask.jsonify({
            'id': new_user.id,
            'user_name': new_user.user_name
        })

    def patch(self):
        current_session = Session()
        input_data = dict(fk_request.json)
        check_password = str(md5(input_data['password'].encode()).hexdigest())
        user_data = current_session.query(UserModel).filter(
            UserModel.user_name == input_data['user_name'],
            UserModel.password == check_password
        ).first()

        if user_data:
            user_data.is_authorized = True
            current_session.commit()
            return flask.jsonify({user_data.id: user_data.is_authorized})
        else:
            raise HttpErrors(400, 'user_name or password uncorrected')


class AdvertisementView(MethodView):
    def get(self):
        current_session = Session()
        advertisement_data = current_session.query(AdvertisementModel).all()
        result = dict()
        for advertisement in advertisement_data:
            result[advertisement.id] = {
                "id": advertisement.id,
                "title": advertisement.title,
                "owner": advertisement.owner
            }

        return flask.jsonify(result)

    def post(self):
        # валидация
        try:
            input_data = AdvertisementValidate(**fk_request.json).dict()
        except pydantic.ValidationError as err:
            raise HttpErrors(400, err.errors())

        current_session = Session()
        new_adv = AdvertisementModel(**input_data)

        current_session.add(new_adv)
        current_session.commit()

        return flask.jsonify({
            'id': new_adv.id,
            'title': new_adv.title
        })

    def patch(self):
        current_session = Session()
        input_data = dict(fk_request.json)
        adv_data = current_session.query(AdvertisementModel).filter(
            AdvertisementModel.id == input_data['id'],
            AdvertisementModel.owner == input_data['owner']
        ).first()

        if adv_data:
            if 'title' in input_data:
                adv_data.title = input_data['title']
            if 'description' in input_data:
                adv_data.description = input_data['description']
            current_session.commit()
        else:
            raise HttpErrors(400, f"invalid input data")

        return flask.jsonify({'result': f"Advertisement №{adv_data.id} successfully changed!"})


    def delete(self):
        current_session = Session()
        input_data = dict(fk_request.json)
        adv_data = current_session.query(AdvertisementModel).filter(
            AdvertisementModel.id == input_data['id'],
            AdvertisementModel.owner == input_data['owner']
        ).first()

        if adv_data:
            current_session.delete(adv_data)
            current_session.commit()

            return flask.jsonify({'result': f"Advertisement №{input_data['id']} successfully delete!"})
        else:
            raise HttpErrors(400, f"invalid input data")


# подключение роутинга
application.add_url_rule(
    '/user/',
    view_func=UserView.as_view('create_user'),
    methods=['GET', 'POST', 'PATCH']
)

# подключение роутинга
application.add_url_rule(
    '/advertisement/',
    view_func=AdvertisementView.as_view('create_advertisement'),
    methods=['GET', 'POST', 'PATCH', 'DELETE']
)


