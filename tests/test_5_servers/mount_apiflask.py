from apiflask import APIFlask, Schema, abort
from apiflask.fields import Integer, String
from apiflask.validators import Length, OneOf
from utilmeta import UtilMeta
from utilmeta.core import api, response

apiflask_app = APIFlask(__name__)

pets = [
    {'id': 0, 'name': 'Kitty', 'category': 'cat'},
    {'id': 1, 'name': 'Coco', 'category': 'dog'}
]


class PetOut(Schema):
    id = Integer()
    name = String()
    category = String()


@apiflask_app.get('/pets/<int:pet_id>')
@apiflask_app.output(PetOut)
def get_pet(pet_id):
    if pet_id > len(pets) - 1:
        abort(404)
    # you can also return an ORM/ODM model class instance directly
    # APIFlask will serialize the object into JSON format
    return pets[pet_id]


class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'


service = UtilMeta(
    __name__,
    name='demo',
    backend=apiflask_app,
    api=RootAPI,
    route='/api'
)

if __name__ == '__main__':
    service.run()
