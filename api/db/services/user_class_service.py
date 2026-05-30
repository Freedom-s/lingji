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
from api.db.db_models import DB, UserClass
from api.db.services.common_service import CommonService
from api.utils import get_uuid, current_timestamp, datetime_format
from api.db import StatusEnum


class UserClassService(CommonService):
    model = UserClass

    @classmethod
    @DB.connection_context()
    def get_by_user(cls, user_id, status=None):
        """获取用户加入的所有班级"""
        query = cls.model.select().where(cls.model.user_id == user_id)
        if status is not None:
            query = query.where(cls.model.status == status)
        return list(query)

    @classmethod
    @DB.connection_context()
    def get_by_class(cls, class_id, status=None):
        """获取班级下的所有用户"""
        query = cls.model.select().where(cls.model.class_id == class_id)
        if status is not None:
            query = query.where(cls.model.status == status)
        return list(query)

    @classmethod
    @DB.connection_context()
    def get_by_user_and_class(cls, user_id, class_id):
        """获取用户在特定班级中的信息"""
        try:
            return cls.model.select().where(
                (cls.model.user_id == user_id) &
                (cls.model.class_id == class_id) &
                (cls.model.status == StatusEnum.VALID.value)
            ).get()
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def add_user_to_class(cls, user_id, class_id, role="student"):
        """添加用户到班级"""
        # 检查是否已存在
        existing = cls.get_by_user_and_class(user_id, class_id)
        if existing:
            # 更新角色和状态
            return cls.model.update(
                role=role,
                status=StatusEnum.VALID.value,
                update_time=current_timestamp(),
                update_date=datetime_format()
            ).where(cls.model.id == existing.id).execute()

        # 创建新记录
        data = {
            "id": get_uuid(),
            "user_id": user_id,
            "class_id": class_id,
            "role": role,
            "status": StatusEnum.VALID.value,
            "create_time": current_timestamp(),
            "create_date": datetime_format(),
            "update_time": current_timestamp(),
            "update_date": datetime_format()
        }
        return cls.model(**data).save(force_insert=True)

    @classmethod
    @DB.connection_context()
    def remove_user_from_class(cls, user_id, class_id):
        """将用户从班级中移除（软删除）"""
        return cls.model.update(
            status="0",
            update_time=current_timestamp(),
            update_date=datetime_format()
        ).where(
            (cls.model.user_id == user_id) &
            (cls.model.class_id == class_id)
        ).execute()

    @classmethod
    @DB.connection_context()
    def update_role(cls, user_id, class_id, role):
        """更新用户在班级中的角色"""
        return cls.model.update(
            role=role,
            update_time=current_timestamp(),
            update_date=datetime_format()
        ).where(
            (cls.model.user_id == user_id) &
            (cls.model.class_id == class_id)
        ).execute()

    @classmethod
    @DB.connection_context()
    def get_class_members_count(cls, class_id):
        """获取班级成员数量"""
        return cls.model.select().where(
            (cls.model.class_id == class_id) &
            (cls.model.status == StatusEnum.VALID.value)
        ).count()

    @classmethod
    @DB.connection_context()
    def is_user_in_class(cls, user_id, class_id):
        """检查用户是否在班级中"""
        return cls.model.select().where(
            (cls.model.user_id == user_id) &
            (cls.model.class_id == class_id) &
            (cls.model.status == StatusEnum.VALID.value)
        ).exists()
