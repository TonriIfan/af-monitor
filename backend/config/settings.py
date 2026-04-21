import os
from pathlib import Path

import pymysql

pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(BASE_DIR / ".env")


def env_list(name: str, default: str) -> list[str]:
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,heartguard.cn,console.heartguard.cn,api.heartguard.cn",
)

INSTALLED_APPS = [
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "accounts",
    "devices",
    "monitoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()

if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "yf_monitor"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"

USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
ML_MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", BASE_DIR / "ml_models"))
DEFAULT_PPG_AF_MODEL_PATH = ML_MODELS_DIR / "ppg_af_model.pkl"
DEFAULT_STRUCTURED_AF_MODEL_PATH = ML_MODELS_DIR / "structured_af_model.pkl"
STRUCTURED_AF_LOOKBACK_MINUTES = int(os.getenv("STRUCTURED_AF_LOOKBACK_MINUTES", "30"))
STRUCTURED_AF_MIN_HISTORY_SAMPLES = int(
    os.getenv("STRUCTURED_AF_MIN_HISTORY_SAMPLES", "5")
)
ALERT_PUSH_MAX_ATTEMPTS = int(os.getenv("ALERT_PUSH_MAX_ATTEMPTS", "3"))
FCM_ENABLED = env_bool("FCM_ENABLED", False)
FCM_CREDENTIALS_FILE = os.getenv("FCM_CREDENTIALS_FILE", "")
FCM_CREDENTIALS_JSON = os.getenv("FCM_CREDENTIALS_JSON", "")
FCM_PROJECT_ID = os.getenv("FCM_PROJECT_ID", "")
FCM_TTL_SECONDS = int(os.getenv("FCM_TTL_SECONDS", "21600"))
ALERT_SSE_POLL_SECONDS = int(os.getenv("ALERT_SSE_POLL_SECONDS", "3"))
ALERT_SSE_HEARTBEAT_SECONDS = int(os.getenv("ALERT_SSE_HEARTBEAT_SECONDS", "15"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://heartguard.cn,https://console.heartguard.cn,https://app.heartguard.cn"
    ),
)
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", True)
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://heartguard.cn,https://console.heartguard.cn,https://app.heartguard.cn,"
        "https://api.heartguard.cn"
    ),
)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
