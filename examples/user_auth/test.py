from server import service
import httpx

if __name__ == '__main__':
    with service.get_client(live=False, backend=httpx) as client:
        r1 = client.post('user/signup', data={
            'username': 'user1',
            'password': '123123'
        })
        print('COOKIES:', r1.cookies, r1.headers)
        r1.print()
        assert r1.status == 200
        assert isinstance(r1.data, dict)
        assert r1.data.get('username') == 'user1'
        r2 = client.get('user')
        assert r2.status == 200
        assert r2.data.get('username') == 'user1'
        r2.print()
        r3 = client.post('user/logout')
        r3.print()
        r4 = client.get('user')
        r4.print()
        assert r4.status == 401
        r5 = client.post('user/login', data={
            'username': 'user1',
            'password': '123123'
        })
        assert r5.status == 200
        assert r5.data.get('username') == 'user1'
        r5.print()
        r6 = client.get('user')
        r6.print()
        assert r6.status == 200
        assert r6.data.get('username') == 'user1'
        r7 = client.put('user', data={
            'username': 'user-updated',
            'password': '123456'
        })
        r7.print()
        assert r7.status == 200
        assert r7.data.get('username') == 'user-updated'
