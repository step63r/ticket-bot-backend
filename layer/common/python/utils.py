import boto3
import requests
import time


dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')


# RELIEF TICKETのURL
base_url = 'https://relief-ticket.jp'

# アーティストとURLに含まれるIDのマッピング
artists = {
    'timelesz': 11,
    'naniwa': 16,
    'yokoyama': 14,
    'jr': 15,
    'news': 24,
    'abc-z': 30,
    'snowman': 31,
}

# アーティスト名と表示名のマッピング
display_names = {
    'timelesz': 'timelesz',
    'naniwa': 'なにわ男子',
    'yokoyama': '横山裕',
    'jr': 'ジュニア',
    'news': 'NEWS',
    'abc-z': 'A.B.C-Z',
    'snowman': 'Snow Man',
}

def get_ssm_parameter(name):
    """SSMパラメーターストアからパラメーターを取得する

    Parameters
    ----------
    name : str
        取得するパラメーターの名前

    Returns
    -------
    str
        パラメーターの値
    """
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    print('get_ssm_parameter response:', response)
    return response['Parameter']['Value']


def get_cached_token():
    """キャッシュされたアクセストークンを取得する

    Returns
    -------
    str
        キャッシュされたアクセストークン or None
    """
    table = dynamodb.Table('TicketAccessTokenCache')
    response = table.get_item(Key={'token_type': 'channel_access_token'})
    print('get_cached_token response:', response)
    item = response.get('Item')
    if item and item['expires_at'] > int(time.time()):
        return item['access_token']
    return None


def fetch_new_token(channel_id: str, channel_secret: str):
    """新しいアクセストークンを取得し、キャッシュに保存する

    Parameters
    ----------
    channel_id : str
        チャネルID
    channel_secret : str
        チャネルシークレット

    Returns
    -------
    str
        新しいアクセストークン
    """
    url = "https://api.line.me/v2/oauth/accessToken"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": channel_id,
        "client_secret": channel_secret
    }
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()  # エラー時に例外を投げる
    print('fetch_new_token response:', response.json())
    token_info = response.json()
    access_token = token_info['access_token']
    expires_in = token_info['expires_in']

    # キャッシュに保存
    table = dynamodb.Table('TicketAccessTokenCache')
    item = {
        'token_type': 'channel_access_token',
        'access_token': access_token,
        'expires_at': int(time.time()) + expires_in - 30
    }
    table.put_item(Item=item)
    print('Token cached:', item)
    return access_token


def get_token(channel_id: str, channel_secret: str):
    """アクセストークンを取得する

    Parameters
    ----------
    channel_id : str
        チャネルID
    channel_secret : str
        チャネルシークレット

    Returns
    -------
    str
        アクセストークン
    """
    cached_token = get_cached_token()
    if cached_token:
        print('Using cached token')
        return cached_token
    else:
        print('Fetching new token')
        return fetch_new_token(channel_id, channel_secret)
