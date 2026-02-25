"""Base Schemas"""
from datetime import datetime
from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# ----------------------------------------------------------------------
# 1. アプリケーションの「核」となるベーススキーマ
# ----------------------------------------------------------------------

class BaseSchema(PydanticBaseModel):
    """
    アプリケーション全体で共通の「核」となるベーススキーマ。
    主にConfigDictの共通設定と共通ヘルパーメソッドを定義します。
    """
    
    model_config = ConfigDict(
        # True: ORMモデルなどの属性からもデータを読み込めるようにする (v1の orm_mode)
        # SQLAlchemyモデルの属性から自動的にPydanticモデルを構築
        from_attributes=True,
        
        # snake_case <-> camelCase の自動エイリアス
        # alias_generator=to_camel,
        
        # True: エイリアス名(camelCase)でもフィールド名(snake_case)でも初期化を許可
        # populate_by_name=True,
        
        # 'forbid': スキーマに定義されていない余分なフィールドを禁止する
        # extra='forbid',
        
        # True: デフォルト値に対してもバリデーションを実行する
        validate_default=True,
        # スキーマ生成時やシリアライズ時にaliasを優先させる設定
        by_alias=True
    )

    # --- 共通ヘルパーメソッド ---
    
    def to_camel_json(self, **kwargs) -> str:
        """
        camelCaseエイリアスを使用し、Noneのフィールドを除外したJSON文字列を返す。
        APIレスポンスの生成に便利です。
        
        :param kwargs: Pydanticの model_dump_json に渡す追加の引数
        """
        # APIレスポンスとして一般的な設定をデフォルトとする
        default_kwargs = {
            "by_alias": True,      # camelCase を使用
            "exclude_none": True,  # 値が None のフィールドはJSONに含めない
        }
        # ユーザーが指定したkwargsでデフォルトを上書き
        default_kwargs.update(kwargs)
        
        return self.model_dump_json(**default_kwargs)

# ----------------------------------------------------------------------
# 2. 読み取り専用（レスポンス用）のベーススキーマ
# ----------------------------------------------------------------------

class ReadOnlySchema(BaseSchema):
    """
    APIレスポンスなど、読み取り専用のスキーマのベース。
    - 共通フィールド (id, created_at など) を持つ
    - インスタンスを不変 (frozen=True) にする
    """
    
    # BaseSchemaのConfigDictを継承し、frozen=True を追加
    model_config = ConfigDict(
        frozen=True,
    )

    # --- 共通フィールド ---
    # APIレスポンス（Readモデル）では、これらのフィールドは必須であることが多い
    
    id: int = Field(description="一意のID")
    created_at: datetime = Field(description="作成日時")
    updated_at: datetime = Field(description="最終更新日時")

# ----------------------------------------------------------------------
# 3. 書き込み可能（リクエスト用）のベーススキーマ
# ----------------------------------------------------------------------

class WriteableSchema(BaseSchema):
    """
    APIリクエストなど、書き込み・変更が可能なスキーマのベース。
    - 値の再代入時にバリデーションを実行する
    """
    
    # BaseSchemaのConfigDictを継承し、validate_assignment=True を追加
    model_config = ConfigDict(
        validate_assignment=True,
    )
    
    # (こちらには id や created_at は（通常）含めない)

class TimestampSchema(BaseSchema):
    """Schema with timestamps"""
    id: int
    created_at: datetime
    updated_at: datetime