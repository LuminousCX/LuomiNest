# LuomiNest コントリビューションガイド (Contributing Guide)

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING_zh.md) | [日本語](CONTRIBUTING_ja.md)

**LuomiNest - 分散型マルチユーザー関係駆動型 AI エージェントプラットフォーム** に関心をお寄せいただき、ありがとうございます！ バグ報告、機能提案、ドキュメントの改善、コードのコントリビューションなど、あらゆる形での貢献を歓迎します。

開発環境のセットアップやワークフローを理解するために、本ガイドラインをお読みください。

---

## 行動規範 (Code of Conduct)

すべてのコントリビューターおよびコミュニティ参加者は、当プロジェクトの [行動規範 (Code of Conduct)](CODE_OF_CONDUCT_ja.md)（[英語版](CODE_OF_CONDUCT.md)）を遵守することが求められます。不適切な行為を発見した場合は、[luminouschenxi@outlook.com](mailto:luminouschenxi@outlook.com) までご連絡ください。

---

## コントリビューションの方法

### 1. バグ報告と機能要望
- **バグ報告**: 報告を作成する前に、既存の [Issues](https://github.com/LuminousCX/LuomiNest/issues) を検索し、同様の問題が既に報告されていないか確認してください。[バグ報告テンプレート](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml) を使用し、再現手順、エラーログ、環境情報を詳しく記載してください。
- **機能要望**: 大規模な機能やアーキテクチャの変更については、事前に [Discussions](https://github.com/LuminousCX/LuomiNest/discussions) で議論するか、[機能要望テンプレート](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml) を利用してユースケースと設計案を共有してください。

### 2. コードコントリビューションの流れ
1. GitHub で本リポジトリを Fork します。
2. `master` ブランチから明確な名前のトピックブランチを作成します：
   ```bash
   git checkout -b feature/your-feature-name
   # または
   git checkout -b fix/issue-description
   ```
3. ローカル環境を構築し、実装と自動テストの作成を行います。
4. ローカルでコードフォーマット、型チェック、テストを実行します。
5. ブランチをプッシュし、本家リポジトリの `master` ブランチに向けて Pull Request を作成します。

---

## ローカル開発環境のセットアップ

### 必要要件
- **Python**: 3.12 以上
- **Node.js**: 22 以上
- **pnpm**: 10.x 以上
- **Docker**: 任意（PostgreSQL、Redis、MQTT などのインフラ検証用）

### バックエンドのセットアップ

```bash
cd backend

# Python 仮想環境の作成と有効化
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 開発用依存関係を編集可能モードでインストール
pip install -e ".[dev]"

# ローカル環境変数の設定
cp config/.env.example config/.env
# config/.env を開き、必要な LLM API キーを設定

# バックエンド開発サーバーの起動
python main.py
```

サーバーはデフォルトで `http://127.0.0.1:18000` で待機します。Swagger API ドキュメントは `http://127.0.0.1:18000/docs` で閲覧できます。

### フロントエンドのセットアップ

```bash
cd frontend

# pnpm で依存関係をインストール
pnpm install

# Vite 開発サーバーおよび Electron を起動
pnpm dev

# 本番ビルド成果物の生成
pnpm build
```

### Docker インフラサービス（任意）

```bash
cd docker

# 開発用コンテナ（PostgreSQL, Redis, MQTT）の起動
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

> **注意**: LuomiNest はデフォルトでローカルの単一 SQLite（WAL モード）で完結動作します。Docker の PostgreSQL や Redis はクラウド拡張および分散テスト環境用として予約されています。

---

## 品質基準とコミット前チェック

Pull Request を送信する前に、以下の静的検証とテストがすべて通過することを確認してください。

### バックエンドのチェック

```bash
cd backend

# 自動テストスイートの実行
pytest tests/

# コードフォーマットと構文チェック
ruff check app tests
ruff format --check app tests

# 厳格な型チェック
mypy app
```

### フロントエンドのチェック

```bash
cd frontend

# Web および Node プロセスの TypeScript 型チェック
pnpm typecheck

# 本番ビルドのコンパイル確認
pnpm build
```

---

## コーディング規約

### Python 規約
- **PEP 8** に厳格に準拠します。
- すべての関数・メソッドに明確な型アノテーション（Type Hints）を付与します。
- フォーマッターには **Ruff** を使用します（1行の最大長: `120` 文字）。
- すべての I/O、データベース操作、ネットワーク通信で `async`/`await` を使用します。
- ワイルドカードインポート（`from x import *`）は禁止です。
- 命名規則：関数・変数は `snake_case`、クラスは `PascalCase`、定数は `UPPER_SNAKE_CASE`。

### TypeScript / Vue 規約
- Vue 3 Composition API と `<script setup lang="ts">` を採用します。
- TypeScript の厳格な型チェックを守り、安易な `any` の使用を避けます。
- グローバル状態は Pinia ストアで一元管理します。
- コンポーネントは `PascalCase.vue`、ユーティリティは `camelCase.ts` とします。

### Git コミット規約 (Conventional Commits)
コミットメッセージは Conventional Commits に従ってください：

形式：`<type>(<scope>): <subject>`

**使用可能なタイプ:**
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント変更
- `style`: コードの動作に影響しないフォーマット変更
- `refactor`: リファクタリング
- `test`: テストコードの追加・修正
- `chore`: ビルドツールや依存関係の更新

**コミットメッセージの例:**
```
feat(memory): メンバー別グループチャットプロファイルトラックを追加
fix(browser): ブラウザツールを読み取り専用ナビゲーションに限定
docs(readme): v0.8.1 リリースのハイライトとリンクを更新
refactor(security): トークン検証と監査ログのマスク処理を統一
```

### ブランチ命名規約
- `feature/<name>` — 新機能の開発
- `fix/<name>` — バグ修正
- `docs/<name>` — ドキュメント修正
- `refactor/<name>` — リファクタリング

---

## モデルアセット配布ポリシー (Avatar / Voice Models)

LuomiNest と共に配布されるモデルアセットファイル（Live2D、PixelPet、PNG Tuber、将来の VRM/Spine モデルなどの内蔵アバターモデル、および内蔵音声モデル）は、**公式保守限定配布ルール**に従います。

### 公式内蔵モデルディレクトリはコアチームのみが保守
以下のパスは、**コミュニティからのアセット追加 PR を受け付けていません**。モデルバイナリの追加や差し替えを目的とした Pull Request はレビューなしでクローズされます：

- `frontend/src/renderer/public/live2d/` — 内蔵 Live2D モデル
- `frontend/src/renderer/public/pixel/` — 内蔵 PixelPet モデル
- `frontend/src/renderer/public/png/` — 内蔵 PNG Tuber モデル
- `backend/models/` — 内蔵音声モデル
- `backend/app/data/avatar-manifest.json` — 内蔵モデルマニフェスト

> ※ モデルローダーの修正やマニフェストスキーマの調整など、コードレベルの改修は歓迎されます。

### このポリシーが存在する理由
1. **著作権と再配布ライセンス**: ネット上に存在する多くのアバターや音声モデルは再配布が許可されていません。公式リポジトリに収録すると、プロジェクトおよび利用者が著作権侵害リスクに晒されます。
2. **レビューの困難さ**: バイナリアーカイブはマルウェア検査やライセンス適合性を自動検証できません。

### ユーザー自身のモデルはローカルに保持
アプリ内の「アバター工房」（**皮套工坊 → モデルのインポート**）を通じてインポートされたモデルは、ローカルのアプリケーションデータディレクトリ（Electron `userData`）に直接コピーされ、**Git リポジトリの管理外**に置かれます。これらはコミットされず、PR で提出してはなりません。

### 新しい公式内蔵モデルの提案
AGPL-3.0 プロジェクトでの無料再配布が明示的に許可されているモデルをお持ちの場合は、まず Issue を作成し、以下を明記してください：
1. モデルの出所および公開ライセンスへのリンク。
2. AGPL-3.0 での再配布許諾の確認。

---

## Pull Request のガイドライン

1. **スコープを絞る**: 1つの PR に複数の無関係な変更を含めないでください。小さな PR ほど迅速にレビューされます。
2. **テンプレートの記入**: [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) の各項目を漏れなく記入してください。
3. **ローカル確認**: テスト、Ruff、Mypy、TypeScript の型チェックがすべて成功していることを事前に確認してください。
4. **フィードバックへの対応**: レビュアーからのコメントには誠実に対応し、建設的な議論を心がけてください。

---

## 内部ドキュメントに関する注意

包括的なアーキテクチャ・設計ドキュメント（`文档/` ディレクトリ）はローカルワークスペース内でのみ提供されており、`.gitignore` によって除外されています。ローカルドラフトを Git にコミットしないようご注意ください。

---

## ライセンスへの同意

LuomiNest へのコントリビューションを行うことで、提出したすべてのコードおよびコンテンツが当プロジェクトの [GNU Affero General Public License v3.0](LICENSE) に基づいてライセンス供与されることに同意したものとみなされます。
