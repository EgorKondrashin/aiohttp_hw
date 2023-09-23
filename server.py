import json
import base64
from aiohttp import web
from models import engine, Base, User, Advertisements, Session
from bcrypt import hashpw, gensalt, checkpw
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from schema import CreateUser, CreateAdvertisement, VALIDATION_CLASS
from pydantic import ValidationError

def hash_password(password:str):
    return hashpw(password.encode(), salt=gensalt()).decode()


def check_password(password: str, hashed_password: str):
    return checkpw(password.encode(), hashed_password=hashed_password.encode())

app = web.Application()


async def orm_context(app):
    print('START')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    print('Shut Down')


@web.middleware
async def sesssion_middleware(request: web.Request, handler):
    async with Session() as session:
        request['session'] = session
        response = await handler(request)
        return response

app.cleanup_ctx.append(orm_context)
app.middlewares.append(sesssion_middleware)

async def get_advertisement(advertisement_id: int, session: Session):
    advertisement = await session.get(Advertisements, advertisement_id)
    if advertisement is None:
        raise web.HTTPNotFound(
            text=json.dumps({'error': 'advertisement not found'}),
            content_type='application/json'
        )
    return advertisement

async def get_user(user_id: int, session: Session):
    user = await session.get(User, user_id)
    if user is None:
        raise web.HTTPNotFound(
            text=json.dumps({'error': 'user not found'}),
            content_type='application/json'
        )
    return user


async def get_user_by_name(name,session):
    result = await session.execute(select(User).where(User.name == name))
    user = result.scalars().first()
    if user is None:
        raise web.HTTPNotFound(
            text=json.dumps({'error': 'user not found'}),
            content_type='application/json'
        )
    return user


class UsersView(web.View):

    @property
    def session(self) -> Session:
        return self.request['session']

    @property
    def user_id(self) -> int:
        return int(self.request.match_info['user_id'])

    async def get(self):
        user = await get_user(self.user_id, self.session)
        return web.json_response({
            'id': user.id,
            'name': user.name,
            'creation_time': int(user.creation_time.timestamp())
        })

    async def post(self):
        json_data = await self.request.json()
        json_data['password'] = hash_password(json_data['password'])
        user = User(**json_data)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as er:
            raise web.HTTPConflict(
                text=json.dumps({"error": "user alredy exists"}),
                content_type='application/json'
            )

        return web.json_response({
            'id': user.id,
        })


class AdvertisementsView(web.View):

    @property
    def user(self):
        return self.request['user']

    @property
    def session(self) -> Session:
        return self.request['session']

    @property
    def advertisement_id(self) -> int:
        return int(self.request.match_info['advertisement_id'])


    async def get(self):
        advertisement = await get_advertisement(self.advertisement_id, self.session)
        return web.json_response({
            'id': advertisement.id,
            'title': advertisement.title,
            'description': advertisement.description,
            'user_id': advertisement.user_id,
        })

    async def post(self):
        decoded_name = base64.b64decode(self.request.headers['Authorization'][6:].strip()).decode('utf-8').split(':')
        user_name = decoded_name[0]
        user = await get_user_by_name(user_name, self.session)
        json_data = await self.request.json()
        json_data['user_id'] = user.id
        advertisement = Advertisements(**json_data)
        self.session.add(advertisement)
        await self.session.commit()
        return web.json_response({
            'id': advertisement.id,
            'title': advertisement.title,
            'description': advertisement.description,
            'user_id': user.id
        })

    async def delete(self):
        advertisement = await get_advertisement(self.advertisement_id, self.session)
        await self.session.delete(advertisement)
        await self.session.commit()
        return web.json_response({'id': advertisement.id})


app.add_routes([
    web.get('/users/{user_id:\d+}', UsersView),
    web.post('/users/', UsersView),
    web.get('/advertisements/{advertisement_id:\d+}', AdvertisementsView),
    web.post('/advertisements/', AdvertisementsView),
    web.delete('/advertisements/{advertisement_id:\d+}', AdvertisementsView),
])


if __name__ == '__main__':
    web.run_app(app)
