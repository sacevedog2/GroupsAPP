import grpc
from concurrent import futures
import logging

from app.grpc.proto import groups_pb2, groups_pb2_grpc
from app.db.database import SessionLocal
from app.db import models

logger = logging.getLogger(__name__)

class GroupsInternalServicer(groups_pb2_grpc.GroupsInternalServicer):
    def CheckMembership(self, request, context):
        db = SessionLocal()
        try:
            if request.scope_type == "group":
                member = db.query(models.GroupMember).filter(
                    models.GroupMember.group_id == request.scope_id,
                    models.GroupMember.user_id == request.user_id
                ).first()
                if member:
                    return groups_pb2.CheckMembershipResponse(is_member=True, role=member.role)
            if request.scope_type == "channel":
                channel_member = db.query(models.ChannelMember).filter(
                    models.ChannelMember.channel_id == request.scope_id,
                    models.ChannelMember.user_id == request.user_id
                ).first()
                if channel_member:
                    group_member = db.query(models.GroupMember).filter(
                        models.GroupMember.group_id == channel_member.group_id,
                        models.GroupMember.user_id == request.user_id
                    ).first()
                    return groups_pb2.CheckMembershipResponse(
                        is_member=True,
                        role=group_member.role if group_member else "member",
                    )
            return groups_pb2.CheckMembershipResponse(is_member=False, role="")
        finally:
            db.close()

    def CheckSharedGroup(self, request, context):
        db = SessionLocal()
        try:
            # Find intersection of group IDs between user 1 and user 2
            groups_1 = db.query(models.GroupMember.group_id).filter(models.GroupMember.user_id == request.user_id_1).subquery()
            groups_2 = db.query(models.GroupMember.group_id).filter(models.GroupMember.user_id == request.user_id_2).subquery()
            
            shared = db.query(groups_1).join(groups_2, groups_1.c.group_id == groups_2.c.group_id).first()
            
            if shared:
                return groups_pb2.CheckSharedGroupResponse(share_group=True)
            return groups_pb2.CheckSharedGroupResponse(share_group=False)
        finally:
            db.close()

async def serve_grpc():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    groups_pb2_grpc.add_GroupsInternalServicer_to_server(GroupsInternalServicer(), server)
    
    from app.core.config import settings
    listen_addr = f'[::]:{settings.GRPC_PORT}'
    server.add_insecure_port(listen_addr)
    logger.info(f"Starting gRPC server on {listen_addr}")
    await server.start()
    return server
