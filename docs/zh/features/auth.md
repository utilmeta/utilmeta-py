# 鉴权系统

### 一个用户登录注册 DEMO

```python
class UserAPI(API):
	 user_config = auth.User(
        User,
        authentication=jwt.JsonWebToken(
            key=env.JWT_SECRET_KEY,
            user_token_field=User.token
        ),
        login_fields=User.username,
        password_field=User.password,
    )
    
	@api.get
    async def get(self, user: User = user_config) -> UserSchema:   
	    # get current user  
        return await UserSchema.ainit(user)
        
    @api.post
    async def signup(self, user: Usersignup = request.Body) -> UserSchema:
        if await User.objects.filter(username=user.username).aexists():
            raise exceptions.BadRequest(f'duplicate username: {repr(user.username)}')
        await user.asave()
        await self.user_config.login_user(
            request=self.request,
            user=user.get_instance(),
        )
        return await UserSchema.ainit(user.pk)

    @api.post
    async def login(self, data: UserLogin = request.Body) -> UserSchema:
        user = await self.user_config.login(
	        self.request, 
	        token=data.email, 
	        password=data.password
	    )
        if not user:
            raise exceptions.PermissionDenied('email or password wrong')
        return await UserSchema.ainit(user)
```


* login
* login_user：login 的底层方法，直接


::: tip
UtilMeta 的鉴权系统也是以插件的方式提供的，如果你希望自行实现鉴权与用户登录注册等，则可以忽略本章节
:::

## 鉴权方式
## Session



## JWT


## OAuth