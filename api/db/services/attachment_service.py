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
from api.db.db_models import Attachment, DB
from api.db.services.common_service import CommonService
from api.db import StatusEnum


class AttachmentService(CommonService):
    model = Attachment

    @classmethod
    @DB.connection_context()
    def get_by_conversation(cls, conversation_id):
        """获取某个对话下所有有效附件"""
        return list(
            cls.model.select().where(
                (cls.model.conversation_id == conversation_id) &
                (cls.model.status == StatusEnum.VALID.value)
            )
        )

    @classmethod
    @DB.connection_context()
    def logical_delete_by_conversation(cls, conversation_id):
        """逻辑删除某个对话下所有附件"""
        return cls.model.update(
            status=StatusEnum.INVALID.value
        ).where(
            cls.model.conversation_id == conversation_id
        ).execute()
