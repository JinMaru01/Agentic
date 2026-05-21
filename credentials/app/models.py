from sqlalchemy import Column, String, Text
from db import Base

class Credential(Base):
    __tablename__ = "credentials"

    id = Column(String, primary_key=True, index=True)
    website = Column(String)
    url = Column(String)
    username = Column(String)
    password = Column(Text)
    category = Column(String)