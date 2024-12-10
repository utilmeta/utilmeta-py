from jwcrypto import jwk, jwe, jwt
from typing import Union
from jwcrypto.common import json_encode, json_decode
from typing import Optional
import base64

RSA_ALGO = 'RSA-OAEP-256'


def generate_key_pair(identifier: str):
    key = jwk.JWK.generate(kty='RSA', size=2048, alg=RSA_ALGO, kid=identifier)
    public_key = key.export_public()
    private_key = key.export_private()
    return public_key, private_key


def encrypt_data(payload, public_key: Union[str, dict]) -> str:
    if not isinstance(public_key, dict):
        if isinstance(public_key, str):
            if not public_key.startswith('{') or not public_key.endswith('}'):
                # BASE64
                public_key = base64.decodebytes(public_key.encode()).decode()

        public_key = json_decode(public_key)
    pubkey_obj = jwk.JWK(**public_key)
    protected_header = {
        "alg": RSA_ALGO,
        "enc": "A256CBC-HS512",
        "typ": "JWE",
        "kid": pubkey_obj.thumbprint(),
    }
    if not isinstance(payload, bytes):
        if isinstance(payload, (dict, list)):
            payload = json_encode(payload)
        else:
            payload = str(payload)
        payload = payload.encode('utf-8')
    jwe_token = jwe.JWE(payload,
                        recipient=pubkey_obj,
                        protected=protected_header)
    return jwe_token.serialize()


def decrypt_data(encrypted: Union[str, bytes], private_key: Union[str, dict]) -> str:
    if isinstance(encrypted, dict):
        encrypted = json_encode(encrypted)
    if not isinstance(private_key, dict):
        private_key = json_decode(private_key)
    privkey_obj = jwk.JWK(**private_key)
    jwetoken = jwe.JWE()
    jwetoken.deserialize(encrypted, key=privkey_obj)
    payload = jwetoken.payload
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8')
    return payload


def decode_token(token: str, public_key: Union[str, dict]) -> Optional[dict]:
    if not isinstance(public_key, dict):
        public_key = json_decode(public_key)
    pubkey_obj = jwk.JWK(**public_key)
    decoded_token = jwt.JWT(key=pubkey_obj, jwt=token)
    try:
        claims = decoded_token.claims
    except KeyError:
        # decode failed
        return None
    return json_decode(claims)
