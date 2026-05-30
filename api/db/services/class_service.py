#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import peewee
from api.db.db_models import DB, Class
from api.db.services.common_service import CommonService
from api.utils import get_uuid, current_timestamp, datetime_format
from api.db import StatusEnum


class ClassService(CommonService):
    model = Class

    @classmethod
    @DB.connection_context()
    def get_by_tenant(cls, tenant_id, status=None):
        """获取租户下的所有班级"""
        query = cls.model.select().where(cls.model.tenant_id == tenant_id)
        if status is not None:
            query = query.where(cls.model.status == status)
        return list(query)

    @classmethod
    @DB.connection_context()
    def get_by_name(cls, tenant_id, name):
        """根据名称获取班级"""
        try:
            return cls.model.select().where(
                (cls.model.tenant_id == tenant_id) &
                (cls.model.name == name) &
                (cls.model.status == StatusEnum.VALID.value)
            ).get()
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def create(cls, tenant_id, name, description=None):
        """创建班级"""
        class_id = get_uuid()
        data = {
            "id": class_id,
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "status": StatusEnum.VALID.value,
            "create_time": current_timestamp(),
            "create_date": datetime_format(),
            "update_time": current_timestamp(),
            "update_date": datetime_format()
        }
        return cls.model(**data).save(force_insert=True)

    @classmethod
    @DB.connection_context()
    def update(cls, class_id, **kwargs):
        """更新班级信息"""
        update_data = {
            "update_time": current_timestamp(),
            "update_date": datetime_format()
        }
        if "name" in kwargs:
            update_data["name"] = kwargs["name"]
        if "description" in kwargs:
            update_data["description"] = kwargs["description"]
        if "status" in kwargs:
            update_data["status"] = kwargs["status"]

        return cls.model.update(update_data).where(cls.model.id == class_id).execute()

    @classmethod
    @DB.connection_context()
    def delete(cls, class_id):
        """删除班级（软删除）"""
        return cls.model.update(
            status="0",
            update_time=current_timestamp(),
            update_date=datetime_format()
        ).where(cls.model.id == class_id).execute()
