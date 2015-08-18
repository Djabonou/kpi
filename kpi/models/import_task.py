import base64
from io import BytesIO
from django.db import models
from shortuuid import ShortUUID
from jsonfield import JSONField
import requests
from pyxform import xls2json_backends
from ..models import Collection
from ..model_utils import create_assets, _load_library_content
from ..zip_importer import HttpContentParse


UID_LENGTH = 22

class ImportTask(models.Model):
    '''
    someting that would be done after the file has uploaded
    ...although we probably would need to store the file in a blob
    '''

    CREATED=    'created'
    PROCESSING= 'processing'
    COMPLETE=   'complete'

    STATUS_CHOICES = (
        (CREATED, CREATED),
        (PROCESSING, PROCESSING),
        (COMPLETE, COMPLETE),
    )

    user = models.ForeignKey('auth.User')
    data = JSONField()
    status = models.CharField(choices=STATUS_CHOICES, max_length=32, default=CREATED)
    uid = models.CharField(max_length=UID_LENGTH, default='')
    date_created = models.DateTimeField(auto_now_add=True)
    # date_expired = models.DateTimeField(null=True)

    def save(self, *args, **kwargs):
        if self.uid == '':
            self.uid = 'i'+ShortUUID().random(UID_LENGTH-1)
        super(ImportTask, self).save(*args, **kwargs)

    def run(self):
        '''
        this could take a while.
        '''
        self.status = self.PROCESSING
        self.save(update_fields=['status'])
        if 'url' in self.data and 'destination' in self.data:
            self._load_assets_from_url(
                self.data['url'], destination=self.data['destination'])
        elif 'base64Encoded' in self.data and 'name' in self.data:
            self._parse_xls_upload(
                base64_encoded_upload=self.data['base64Encoded'],
                name=self.data['name']
            )
        else:
            raise Exception(
                'ImportTask data must contain both `base64Encoded` and `name` '
                'or both `url` and `destination`'
            )
        # TODO: record failures; possibly clear self.data after success
        self.status = self.COMPLETE
        self.save(update_fields=['status'])

    def _load_assets_from_url(self, url, destination):
        req = requests.get(url, allow_redirects=True)
        fif = HttpContentParse(request=req).parse()
        fif.remove_invalid_assets()
        fif.remove_empty_collections()
        destination_collection = False

        collections_to_assign = []
        for item in fif._parsed:
            kwargs = {
                'owner': self.user,
                'name': item._name_base,
            }
            if destination:
                destination_collection = Collection.objects.get(owner=self.user, uid=destination)

            if item.get_type() == 'collection':
                item._orm = create_assets(item.get_type(), kwargs)
            elif item.get_type() == 'asset':
                kontent = xls2json_backends.xls_to_dict(item.readable)
                content = {}
                for key, val in kontent.items():
                    if not key.endswith('_header'):
                        content[key] = val
                kwargs['asset_type'] = 'survey_block'
                kwargs['content'] = content
                item._orm = create_assets(item.get_type(), kwargs)
            if item.parent:
                collections_to_assign.append([
                    item._orm,
                    item.parent._orm,
                ])
            elif destination_collection:
                collections_to_assign.append([
                    item._orm,
                    destination_collection,
                ])

        for (orm_obj, parent_item) in collections_to_assign:
            if hasattr(orm_obj, 'parent'):
                orm_obj.parent = parent_item
            else:
                orm_obj.parent = parent_item
            orm_obj.save()

    def _parse_xls_upload(self, base64_encoded_upload, name):
        decoded_str = base64.b64decode(base64_encoded_upload)
        survey_dict = xls2json_backends.xls_to_dict(BytesIO(decoded_str))
        survey_dict_keys = survey_dict.keys()
        if 'library' in survey_dict_keys:
            collection = _load_library_content({
                    'content': survey_dict,
                    'owner': self.user,
                    'name': name
                })
        elif 'survey' in survey_dict_keys or 'block' in survey_dict_keys:
            asset = Asset.objects.create(
                owner=self.user,
                content=survey_dict,
                name=name
            )