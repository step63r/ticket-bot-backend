import boto3
import json
import requests


dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')


BUTTON_CHECK_CURRENT_ARTIST = '現在の設定を確認'
BUTTON_CHANGE_ARTIST = '設定を変更'


MESSAGE_SELECT_ARTIST = {
    "type": "flex",
    "altText": "アーティストを選択してください。",
    "contents": {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                { "type": "text", "text": "対象のアーティストを選択してください", "weight": "bold", "size": "md", "wrap": True },
                { "type": "button", "action": { "type": "postback", "label": "timelesz", "data": "artist=timelesz" } },
                { "type": "button", "action": { "type": "postback", "label": "なにわ男子", "data": "artist=naniwa" } },
                { "type": "button", "action": { "type": "postback", "label": "横山裕", "data": "artist=yokoyama" } },
                { "type": "button", "action": { "type": "postback", "label": "ジュニア", "data": "artist=jr" } },
                { "type": "button", "action": { "type": "postback", "label": "NEWS", "data": "artist=news" } }
            ]
        }
    }
}


# アーティスト名と表示名のマッピング
display_names = {
    'timelesz': 'timelesz',
    'naniwa': 'なにわ男子',
    'yokoyama': '横山裕',
    'jr': 'ジュニア',
    'news': 'NEWS'
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


def get_channel_access_token(channel_id: str, channel_secret: str):
    """LINEのステートレスチャネルアクセストークンを取得する

    Parameters
    ----------
    channel_id : str
        チャネルID
    channel_secret : str
        チャネルシークレット

    Returns
    -------
    str
        ステートレスチャネルアクセストークン
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

    token_info = response.json()
    print('get_channel_access_token response:', token_info)
    return token_info['access_token']


def handle_message(event: any):
    """ユーザーからのメッセージイベントの処理

    Parameters
    ----------
    event : any
        イベントデータ
    """
    print('handle_message event:', event)
    user_id = event['source']['userId']
    reply_token = event['replyToken']
    message_text = event['message']['text']
    reply_messages = []

    if message_text == BUTTON_CHECK_CURRENT_ARTIST:
        # TicketBotUsersからユーザーのアーティスト設定を取得
        table = dynamodb.Table('TicketBotUsers')
        response = table.get_item(Key={'userId': user_id})
        if 'Item' in response:
            artist = response['Item'].get('artist', '未設定')
            reply_messages.append({
                "type": "text",
                "text": f"現在のアーティスト設定: {display_names.get(artist, artist)}"
            })
        else:
            reply_messages.append({
                "type": "text",
                "text": "アーティスト設定が見つかりません。設定を行ってください。"
            })

    elif message_text == BUTTON_CHANGE_ARTIST:
        reply_messages.append(MESSAGE_SELECT_ARTIST)

    else:
        reply_messages.append({
            "type": "text",
            "text": "そのメッセージは認識できませんでした。メニューから選択してください。",
        })

    # ユーザーに返信メッセージを送信
    token = get_channel_access_token(
        get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
        get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    message = {
        "replyToken": reply_token,
        "messages": reply_messages
    }
    response = requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers=headers,
        json=message
    )
    response.raise_for_status()  # エラー時に例外を投げる
    print('handle_message response:', response.json())


def handle_follow(event: any):
    """友だち追加イベントの処理

    Parameters
    ----------
    event : any
        イベントデータ
    """
    print('handle_follow event:', event)
    user_id = event['source']['userId']
    token = get_channel_access_token(
        get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
        get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'to': user_id,
        'messages': [MESSAGE_SELECT_ARTIST]
    }
    response = requests.post(
        'https://api.line.me/v2/bot/message/push',
        headers=headers,
        json=payload
    )
    response.raise_for_status()  # エラー時に例外を投げる
    print('handle_follow response:', response.json())


def handle_unfollow(event: any):
    """友だち解除イベントの処理

    Parameters
    ----------
    event : any
        イベントデータ
    """
    print('handle_unfollow event:', event)
    user_id = event['source']['userId']
    table = dynamodb.Table('TicketBotUsers')
    table.delete_item(
        Key={
            'userId': user_id
        }
    )


def handle_postback(event: any):
    """リッチメニューなどからのアクションイベントの処理

    Parameters
    ----------
    event : any
        イベントデータ
    """
    print('handle_postback event:', event)

    # 選択結果をDynamoDBに保存
    user_id = event['source']['userId']
    postback_data = event['postback']['data']
    artist = postback_data.split('artist=')[-1]
    table = dynamodb.Table('TicketBotUsers')
    table.put_item(
        Item={
            'userId': user_id,
            'artist': artist
        }
    )

    # ユーザーに登録完了のメッセージを送信
    reply_token = event['replyToken']
    message = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": f"{display_names[artist]} を登録しました。"
            }
        ]
    }
    token = get_channel_access_token(
        get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
        get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers=headers,
        json=message
    )
    response.raise_for_status()  # エラー時に例外を投げる
    print('handle_postback response:', response.json())


def lambda_handler(event, context):
    """push_notification Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    print('event', event)

    try:
        body = json.loads(event['body'])
        for e in body.get('events', []):
            event_type = e.get('type')
            if event_type == 'message':     # ユーザーからのメッセージ
                handle_message(e)

            elif event_type == 'follow':    # 友だち追加
                handle_follow(e)

            elif event_type == 'unfollow':  # 友だち解除
                handle_unfollow(e)

            elif event_type == 'join':      # グループや複数人トークへの参加
                pass

            elif event_type == 'leave':     # グループや複数人トークからの退出
                pass

            elif event_type == 'postback':  # リッチメニューなどからのアクション
                handle_postback(e)

            elif event_type == 'beacon':    # ビーコン検知イベント
                pass

    except Exception as e:
        # エラーが発生した場合、管理者に通知
        print('Error:', e)
        token = get_channel_access_token(
            get_ssm_parameter('TICKET_LINE_CHANNEL_ID'),
            get_ssm_parameter('TICKET_LINE_CHANNEL_SECRET')
        )
        admin_line_user_id = get_ssm_parameter('TICKET_ADMIN_LINE_USER_ID')

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        message = {
            'to': admin_line_user_id,
            'messages': [
                {
                    'type': 'text',
                    'text': f'Error occurred in check_ticket: {str(e)}'
                }
            ]
        }
        response = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers=headers,
            json=message
        )
        response.raise_for_status()  # エラー時に例外を投げる
        print('Error notification response:', response.json())

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {'Content-Type': 'application/json'}
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Event processed successfully'
        }),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
