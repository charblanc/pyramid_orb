import orb

from pyramid.httpexceptions import HTTPForbidden, HTTPBadRequest, HTTPNotFound
from pyramid_orb.utils import get_context
from pyramid_orb.service import OrbService


class CollectionService(OrbService):
    def __init__(self, request, collection, parent=None, name=None):
        super(CollectionService, self).__init__(request=request, parent=parent, name=name)

        self.collection = collection
        if isinstance(collection, orb.Collection):
            self.model = collection.model()
        else:
            self.model = None

    def __getitem__(self, key):
        try:
            record_id = int(key)
        except ValueError:
            record_id = key

        if self.model is None:
            raise HTTPNotFound()

        from .model import ModelService
        return ModelService(self.request,
                            self.model,
                            record_id=record_id,
                            parent=self,
                            from_collection=self.collection)

    def get(self):
        if self.model is not None:
            values, context = get_context(self.request, model=self.model)
            if values:
                where = orb.Query.build(values)
                context.where = where & context.where
            return self.collection.refine(context=context)
        else:
            return self.collection

    def put(self):
        if self.model is None:
            raise HTTPBadRequest()

        _, context = get_context(self.request, model=self.model)

        try:
            params = self.request.json_body
        except StandardError:
            params = self.request.params

        try:
            records = params['records']
        except KeyError:
            raise HTTPBadRequest()
        else:
            update_records = []

            # create any records that need creating first
            for record in records:
                if isinstance(record, dict):
                    record = self.model.create(record, context=context)
                else:
                    record = self.model(record)

                update_records.append(record)

            # update the collection with the new records
            return self.collection.update(update_records, context=context)

    def post(self):
        if self.model is None:
            raise HTTPBadRequest()

        if self.collection.pipe():
            values, context = get_context(self.request, model=self.collection.pipe().throughModel())
        else:
            values, context = get_context(self.request, model=self.model)

        return self.collection.create(values, context=context)

    def permitted(self):
        method = self.request.method.lower()
        auth = getattr(self.model, '__auth__', None)

        if callable(auth):
            return auth(scope={'request': self.request})

        elif isinstance(auth, dict):
            try:
                method_auth = auth[method]
            except KeyError:
                raise HTTPForbidden()
            else:
                if callable(method_auth):
                    return method_auth(self.request)
                elif method_auth:
                    return self.request.has_permission(method_auth)
                else:
                    return True

        elif isinstance(auth, (list, tuple, set)):
            return method in auth

        elif auth:
            return self.request.has_permission(auth)

        else:
            return True

    @classmethod
    def routes(cls, obj):
        return {}