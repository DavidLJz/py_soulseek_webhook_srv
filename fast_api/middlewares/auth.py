from typing import Annotated
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse

from json import loads

from decouple import config

class Identity():
  def __init__(self):
    """
    Validación de la identidad del usuario
    """
    self._SERVER_KEY = config('SERVER_KEY')
    self._RECORD = config('USERS', cast=loads)
    self._ALGORITHM = config('ALGORITHM', 'HS256')
    self._ACCESS_TOKEN_EXPIRE_HOURS = config('ACC_TOKEN_EXPIRE_HOURS', default=12, cast=int)

  def create_token(self, name, password):
    username = self.exists(name)
    if not username:
      raise self._except('Incorrect username')
    if not self.verify_password(password, username['hashed_password']):
      raise self._except('Incorrect password')
    data={ "sub": name }
    expires_delta = timedelta(hours=self._ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = data.copy()
    if expires_delta:
      expire = datetime.now(timezone.utc) + expires_delta
    else:
      expire = datetime.now(timezone.utc) + timedelta(hours=12)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, self._SERVER_KEY, algorithm=self._ALGORITHM)
    
    return JSONResponse(content={
      "access_token": encoded_jwt,
      "token_type": 'bearer',
      },status_code=200) 

  def decode(self, token):
    return jwt.decode(token, self._SERVER_KEY, algorithms=[self._ALGORITHM])
  
  def verify_password(self, plain_password:str, hashed_password:str):
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

  def exists(self, username: str):
    if username not in self._RECORD:
      return None
    if self._RECORD[username].get('disabled', False):
      return None
    return self._RECORD[username]

  def _except(self, detail:str=''):
    return HTTPException(
      status_code=401,
      detail=detail,
      headers={"WWW-Authenticate": "Bearer"},
    ) 


def validate_request(token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl="token"))]):
  """Middleware para la validacion de peticiones"""  
  try:
    verify = Identity()
    name = verify.decode(token).get("sub")
    if name is None:
      raise verify._except('Could not validate credentials1')
    
    user = verify.exists(name)
    if user is None:
      raise verify._except('Could not validate credentials2') 
  
  except InvalidTokenError:
   raise verify._except('Could not validate credentials3')