# ticket-bot-backend

## Description

The backend logic for LINE bot to notify _RELIEF Ticket_ Resale platform.

## Requirement

- Visual Studio Code
  - AWS Toolkit
- Python 3.13
- Amazon Web Services
  - API Gateway
  - Lambda
  - DynamoDB
  - Systems Manager

## Python Package Requirements

```
beautifulsoup4==4.13.4
boto3==1.40.5
requests==2.32.4
```

## SSM (Parameter Store) Requirements

### TICKET_ADMIN_LINE_USER_ID (String)

Specify the LINE user ID to notify of error logs.

### TICKET_LINE_CHANNEL_ID (String)

Specify the LINE channel ID of the bot.

### TICKET_LINE_CHANNEL_SECRET (String)

Specify the LINE channel secret of the bot.

## Install

Fork and clone this repository.

```
$ git clone git@github.com:yourname/ticket-bot-backend.git
```

Install layer packages.

```
$ cd ./layer/common
$ pip install -r ./requirements.txt -t ./python
```

SAM build and deploy.

```
$ sam build
$ sam deploy --guided
```

## Usage

Deploy your AWS account as SAM application.

## Contribution

1. Fork this repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create new Pull Request

## License

MIT License

## Author

[minato](https://www.minatoproject.com/)
