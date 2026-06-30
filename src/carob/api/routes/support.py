import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from carob.api.deps import current_customer
from carob.api.schemas import ConversationOut, ConversationWithMessages, MessageIn, MessageOut, PostedMessage
from carob.db import get_session
from carob.errors import NotFound
from carob.models import Customer, SupportConversation
from carob.support import service
from carob.support.router import get_router

router = APIRouter(prefix="/v1/support", tags=["support"])


@router.post("/messages", status_code=201, response_model=PostedMessage)
def post_message(
    body: MessageIn, customer: Customer = Depends(current_customer), session: Session = Depends(get_session)
) -> PostedMessage:
    conversation, message = service.receive_customer_message(
        session, get_router(), customer, body.body, body.conversation_id
    )
    return PostedMessage(
        conversation=ConversationOut.model_validate(conversation), message=MessageOut.model_validate(message)
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
def get_conversation(
    conversation_id: uuid.UUID,
    customer: Customer = Depends(current_customer),
    session: Session = Depends(get_session),
) -> ConversationWithMessages:
    conversation = session.get(SupportConversation, conversation_id)
    if conversation is None or conversation.customer_id != customer.id:
        raise NotFound("conversation not found")
    return ConversationWithMessages(
        conversation=ConversationOut.model_validate(conversation),
        messages=[MessageOut.model_validate(m) for m in service.messages(session, conversation.id)],
    )
