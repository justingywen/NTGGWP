
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / '.env')

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-!myfgv08#hs01651h)z0w9m48ywynf10)135pb!5tnmn%zug2n',
)

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
ALLOWED_HOSTS += [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.nav_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

LOGIN_URL = 'login'

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('DB_NAME', 'course_platform_db'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '1433'),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {
            'driver': os.environ.get('DB_ODBC_DRIVER', 'ODBC Driver 18 for SQL Server'),
            # Azure SQL Database 要求連線加密；本機 SQL Server 若未裝憑證可將
            # TrustServerCertificate 改 yes（僅限開發環境）。
            'extra_params': os.environ.get(
                'DB_EXTRA_PARAMS',
                'Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;',
            ),
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'zh-hant'

TIME_ZONE = 'Asia/Taipei'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

AZURE_ACCOUNT_NAME = os.environ.get('AZURE_ACCOUNT_NAME', '')
if AZURE_ACCOUNT_NAME:
    AZURE_CONTAINER = os.environ.get('AZURE_CONTAINER', 'media')
    _azure_key = os.environ.get('AZURE_ACCOUNT_KEY', '')
    _azure_sas = os.environ.get('AZURE_SAS_TOKEN', '')
    if _azure_key:
        AZURE_ACCOUNT_KEY = _azure_key
    elif _azure_sas:
        AZURE_SAS_TOKEN = _azure_sas
    _azure_custom_domain = os.environ.get('AZURE_CUSTOM_DOMAIN', '')
    if _azure_custom_domain:
        AZURE_CUSTOM_DOMAIN = _azure_custom_domain
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.azure_storage.AzureStorage',
        'OPTIONS': {'location': 'media'},
    }

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL') or EMAIL_HOST_USER or 'noreply@example.com'

GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')

LINE_LOGIN_CHANNEL_ID = os.environ.get('LINE_LOGIN_CHANNEL_ID', '')
LINE_LOGIN_CHANNEL_SECRET = os.environ.get('LINE_LOGIN_CHANNEL_SECRET', '')

# Microsoft Entra ID（Azure AD）SSO，供學生用學校 / 個人 Microsoft 帳號登入。
# TENANT 預設 'common'（個人 + 組織帳號皆可），限定學校租戶請填該校的 Tenant ID
# 或 'organizations'（僅限組織帳號，排除個人 Microsoft 帳號）。
MICROSOFT_OAUTH_CLIENT_ID = os.environ.get('MICROSOFT_OAUTH_CLIENT_ID', '')
MICROSOFT_OAUTH_CLIENT_SECRET = os.environ.get('MICROSOFT_OAUTH_CLIENT_SECRET', '')
MICROSOFT_OAUTH_TENANT_ID = os.environ.get('MICROSOFT_OAUTH_TENANT_ID', 'common')

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
AI_ASSISTANT_MODEL = os.environ.get('AI_ASSISTANT_MODEL', 'claude-opus-5')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
AI_PROVIDER = os.environ.get('AI_PROVIDER', '')

GEMINI_MARKETING_MODEL = os.environ.get('GEMINI_MARKETING_MODEL', 'gemini-3.6-flash')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
