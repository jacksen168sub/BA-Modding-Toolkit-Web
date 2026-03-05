from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "BA-Modding-Toolkit Web"
    DEBUG: bool = True
    
    # File storage paths
    # Path(__file__) = backend/app/config.py
    # .parent = backend/app
    # .parent.parent = backend
    # .parent.parent.parent = BA-Modding-Toolkit-Web/ (project root)
    BASE_DIR: Path = Path(__file__).parent.parent  # backend/
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent  # BA-Modding-Toolkit-Web/
    
    # Database - use absolute path
    @property
    def DATABASE_URL(self) -> str:
        db_path = self.PROJECT_ROOT / "data" / "bamt.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"
    TEMP_DIR: str = "storage/temp"
    
    # Expiration settings
    SESSION_EXPIRE_HOURS: int = 24
    
    # Cleanup settings
    CLEANUP_INTERVAL_HOURS: int = 1
    
    # File upload limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: set = {".bundle", ".png", ".skel", ".atlas"}
    
    # CLI settings
    CLI_TIMEOUT: int = 600  # 10 minutes

    # Concurrency settings
    MAX_CONCURRENT_TASKS: int = 2  # Maximum concurrent tasks
    
    @property
    def upload_path(self) -> Path:
        return self.PROJECT_ROOT / self.UPLOAD_DIR
    
    @property
    def output_path(self) -> Path:
        return self.PROJECT_ROOT / self.OUTPUT_DIR
    
    @property
    def temp_path(self) -> Path:
        return self.PROJECT_ROOT / self.TEMP_DIR

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()