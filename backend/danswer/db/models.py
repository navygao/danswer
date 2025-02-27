import datetime
from enum import Enum as PyEnum
from typing import Any
from typing import List
from typing import Optional
from uuid import UUID

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from danswer.auth.schemas import UserRole
from danswer.configs.constants import DocumentSource
from danswer.connectors.models import InputType
from danswer.datastores.interfaces import StoreType


class IndexingStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


# these may differ in the future, which is why we're okay with this duplication
class DeletionStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    # even an almost empty token from keycloak will not fit the default 1024 bytes
    access_token: Mapped[str] = mapped_column(Text(), nullable=False)  # type: ignore


class User(SQLAlchemyBaseUserTableUUID, Base):
    oauth_accounts: Mapped[List[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined"
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, default=UserRole.BASIC)
    )
    credentials: Mapped[List["Credential"]] = relationship(
        "Credential", back_populates="user", lazy="joined"
    )


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    pass


class ConnectorCredentialPair(Base):
    """Connectors and Credentials can have a many-to-many relationship
    I.e. A Confluence Connector may have multiple admin users who can run it with their own credentials
    I.e. An admin user may use the same credential to index multiple Confluence Spaces
    """

    __tablename__ = "connector_credential_pair"
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector.id"), primary_key=True
    )
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("credential.id"), primary_key=True
    )
    # Time finished, not used for calculating backend jobs which uses time started (created)
    last_successful_index_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_attempt_status: Mapped[IndexingStatus | None] = mapped_column(
        Enum(IndexingStatus)
    )
    total_docs_indexed: Mapped[int] = mapped_column(Integer, default=0)

    connector: Mapped["Connector"] = relationship(
        "Connector", back_populates="credentials"
    )
    credential: Mapped["Credential"] = relationship(
        "Credential", back_populates="connectors"
    )


class Connector(Base):
    __tablename__ = "connector"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    source: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, native_enum=False)
    )
    input_type = mapped_column(Enum(InputType, native_enum=False))
    connector_specific_config: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB()
    )
    refresh_freq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    time_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)

    credentials: Mapped[List["ConnectorCredentialPair"]] = relationship(
        "ConnectorCredentialPair",
        back_populates="connector",
        cascade="all, delete-orphan",
    )
    documents_by_connector: Mapped[
        List["DocumentByConnectorCredentialPair"]
    ] = relationship("DocumentByConnectorCredentialPair", back_populates="connector")
    index_attempts: Mapped[List["IndexAttempt"]] = relationship(
        "IndexAttempt", back_populates="connector"
    )
    deletion_attempt: Mapped[Optional["DeletionAttempt"]] = relationship(
        "DeletionAttempt", back_populates="connector"
    )


class Credential(Base):
    __tablename__ = "credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    credential_json: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB())
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    public_doc: Mapped[bool] = mapped_column(Boolean, default=False)
    time_created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    time_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    connectors: Mapped[List["ConnectorCredentialPair"]] = relationship(
        "ConnectorCredentialPair",
        back_populates="credential",
        cascade="all, delete-orphan",
    )
    documents_by_credential: Mapped[
        List["DocumentByConnectorCredentialPair"]
    ] = relationship("DocumentByConnectorCredentialPair", back_populates="credential")
    index_attempts: Mapped[List["IndexAttempt"]] = relationship(
        "IndexAttempt", back_populates="credential"
    )
    deletion_attempt: Mapped[Optional["DeletionAttempt"]] = relationship(
        "DeletionAttempt", back_populates="credential"
    )
    user: Mapped[User] = relationship("User", back_populates="credentials")


class IndexAttempt(Base):
    """
    Represents an attempt to index a group of 1 or more documents from a
    source. For example, a single pull from Google Drive, a single event from
    slack event API, or a single website crawl.
    """

    __tablename__ = "index_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int | None] = mapped_column(
        ForeignKey("connector.id"),
        nullable=True,
    )
    credential_id: Mapped[int | None] = mapped_column(
        ForeignKey("credential.id"),
        nullable=True,
    )
    status: Mapped[IndexingStatus] = mapped_column(Enum(IndexingStatus))
    error_msg: Mapped[str | None] = mapped_column(
        String(), default=None
    )  # only filled if status = "failed"
    time_created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    time_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    connector: Mapped[Connector] = relationship(
        "Connector", back_populates="index_attempts"
    )
    credential: Mapped[Credential] = relationship(
        "Credential", back_populates="index_attempts"
    )

    def __repr__(self) -> str:
        return (
            f"<IndexAttempt(id={self.id!r}, "
            f"connector_id={self.connector_id!r}, "
            f"status={self.status!r}, "
            f"error_msg={self.error_msg!r})>"
            f"time_created={self.time_created!r}, "
            f"time_updated={self.time_updated!r}, "
        )


class DeletionAttempt(Base):
    """Represents an attempt to delete all documents indexed by a specific
    connector / credential pair.
    """

    __tablename__ = "deletion_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector.id"),
    )
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("credential.id"),
    )
    status: Mapped[DeletionStatus] = mapped_column(Enum(DeletionStatus))
    num_docs_deleted: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(
        String(), default=None
    )  # only filled if status = "failed"
    time_created: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    time_updated: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    connector: Mapped[Connector] = relationship(
        "Connector", back_populates="deletion_attempt"
    )
    credential: Mapped[Credential] = relationship(
        "Credential", back_populates="deletion_attempt"
    )


class Document(Base):
    """Represents a single documents from a source. This is used to store
    document level metadata so we don't need to duplicate it in a bunch of
    DocumentByConnectorCredentialPair's/Chunk's for documents
    that are split into many chunks and/or indexed by many connector / credential
    pairs."""

    __tablename__ = "document"

    # this should correspond to the ID of the document (as is passed around
    # in Danswer)
    id: Mapped[str] = mapped_column(String, primary_key=True)

    document_store_entries: Mapped["Chunk"] = relationship(
        "Chunk", back_populates="document"
    )


class DocumentByConnectorCredentialPair(Base):
    """Represents an indexing of a document by a specific connector / credential
    pair"""

    __tablename__ = "document_by_connector_credential_pair"

    id: Mapped[str] = mapped_column(ForeignKey("document.id"), primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("connector.id"), primary_key=True
    )
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("credential.id"), primary_key=True
    )

    connector: Mapped[Connector] = relationship(
        "Connector", back_populates="documents_by_connector"
    )
    credential: Mapped[Credential] = relationship(
        "Credential", back_populates="documents_by_credential"
    )


class Chunk(Base):
    """A row represents a single entry in a document store (e.g. a single chunk
    in Qdrant/Typesense)"""

    __tablename__ = "chunk"

    # this should correspond to the ID in the document store
    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_store_type: Mapped[StoreType] = mapped_column(
        Enum(StoreType), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id"))

    document: Mapped[Document] = relationship(
        "Document", back_populates="document_store_entries"
    )
