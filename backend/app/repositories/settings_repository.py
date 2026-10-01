import contextlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decrypt_secret
from backend.app.db.models import LLMProviderModel, Setting
from backend.app.llm.defaults import get_default_roles_config
from backend.app.llm.types import ModelRolesConfig


class SettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_setting(self, key: str) -> Setting | None:
        result = await self.db.execute(select(Setting).where(Setting.key == key))
        return result.scalar_one_or_none()

    async def set_setting(self, key: str, value_json: str, category: str = "general") -> Setting:
        setting = await self.get_setting(key)
        if setting:
            setting.value_json = value_json
            setting.category = category
        else:
            setting = Setting(key=key, value_json=value_json, category=category)
            self.db.add(setting)
        await self.db.flush()
        return setting

    async def get_model_roles_config(self) -> ModelRolesConfig:
        setting = await self.get_setting("llm_model_roles")
        if not setting or not setting.value_json:
            return get_default_roles_config()
        try:
            data = json.loads(setting.value_json)
            return ModelRolesConfig.model_validate(data)
        except Exception:
            return get_default_roles_config()

    async def save_model_roles_config(self, config: ModelRolesConfig) -> Setting:
        json_val = json.dumps(config.model_dump())
        return await self.set_setting("llm_model_roles", json_val, category="llm")

    async def get_decrypted_provider_keys(self, encryption_key: str) -> dict[str, str]:
        result = await self.db.execute(select(LLMProviderModel).where(LLMProviderModel.enabled))
        providers = result.scalars().all()
        keys: dict[str, str] = {}
        for p in providers:
            if p.encrypted_api_key:
                with contextlib.suppress(Exception):
                    decrypted = decrypt_secret(p.encrypted_api_key, encryption_key)
                    keys[p.name.lower()] = decrypted
        return keys

    async def get_hotkey(self) -> str:
        setting = await self.get_setting("shell_hotkey")
        if setting and setting.value_json:
            try:
                data = json.loads(setting.value_json)
                return str(data.get("hotkey", "Ctrl+Space"))
            except Exception:
                pass
        return "Ctrl+Space"

    async def save_hotkey(self, hotkey: str) -> Setting:
        from pathlib import Path

        json_val = json.dumps({"hotkey": hotkey})
        setting = await self.set_setting("shell_hotkey", json_val, category="system")
        try:
            config_path = Path("storage/shell_config.json")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json_val, encoding="utf-8")
        except Exception:
            pass
        return setting
