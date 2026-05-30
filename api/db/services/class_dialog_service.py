#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License).
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
from api.db.db_models import DB, ClassDialog
from api.db.services.common_service import CommonService
from api.utils import get_uuid, current_timestamp, datetime_format


class ClassDialogService(CommonService):
    model = ClassDialog

    @classmethod
    @DB.connection_context()
    def get_by_class(cls, class_id):
        """获取班级的所有对话"""
        query = cls.model.select().where(cls.model.class_id == class_id)
        return list(query)

    @classmethod
    @DB.connection_context()
    def get_by_dialog(cls, dialog_id):
        """获取对话所属的班级"""
        try:
            return cls.model.select().where(
                cls.model.dialog_id == dialog_id
            ).get()
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def link_dialog_to_class(cls, class_id, dialog_id):
        """将对话关联到班级"""
        # 检查是否已存在
        existing = cls.model.select().where(
            (cls.model.class_id == class_id) &
            (cls.model.dialog_id == dialog_id)
        ).first()

        if existing:
            return existing.id

        # 创建新关联
        data = {
            "id": get_uuid(),
            "class_id": class_id,
            "dialog_id": dialog_id,
            "create_time": current_timestamp(),
            "create_date": datetime_format(),
            "update_time": current_timestamp(),
            "update_date": datetime_format()
        }
        return cls.model(**data).save(force_insert=True)

    @classmethod
    @DB.connection_context()
    def unlink_dialog_from_class(cls, class_id, dialog_id):
        """解除对话与班级的关联"""
        return cls.model.delete().where(
            (cls.model.class_id == class_id) &
            (cls.model.dialog_id == dialog_id)
        ).execute()

    @classmethod
    @DB.connection_context()
    def unlink_all_from_class(cls, class_id):
        """解除班级下所有对话的关联"""
        return cls.model.delete().where(
            cls.model.class_id == class_id
        ).execute()

    @classmethod
    @DB.connection_context()
    def unlink_all_from_dialog(cls, dialog_id):
        """解除对话与所有班级的关联"""
        return cls.model.delete().where(
            cls.model.dialog_id == dialog_id
        ).execute()

    @classmethod
    @DB.connection_context()
    def is_dialog_in_class(cls, class_id, dialog_id):
        """检查对话是否在班级中"""
        return cls.model.select().where(
            (cls.model.class_id == class_id) &
            (cls.model.dialog_id == dialog_id)
        ).exists()

    @classmethod
    @DB.connection_context()
    def get_class_dialogs_count(cls, class_id):
        """获取班级对话数量"""
        return cls.model.select().where(
            cls.model.class_id == class_id
        ).count()
