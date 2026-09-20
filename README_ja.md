<div align="center">

<img src="frontend/resources/icon.svg" alt="LuomiNest Logo" width="120" height="120" />

# LuomiNest

**分散型マルチユーザー関係駆動型 AI エージェントプラットフォーム**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.8.1-green.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-44-47848F.svg?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CodeRabbit](https://img.shields.io/endpoint?url=https://coderabbit.ai/api/badges/LuminousCX/LuomiNest&label=CodeRabbit)](https://coderabbit.ai)
[![GitHub Stars](https://img.shields.io/github/stars/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/issues)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/commits/master)
[![Code Size](https://img.shields.io/github/languages/code-size/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest)

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

</div>

---

<a id="luominest"></a>

## 概要

LuomiNest は、オープンソースの**分散型マルチユーザー関係駆動型 AI エージェントプラットフォーム**です。「関係駆動」を核とした設計思想に基づき、マスター／スレーブの2層メモリ構造を通じて、グループチャット内で各ユーザーの個別プロファイル（スレーブメモリ）を自動抽出し、プライベートチャット時にはそのユーザー固有のコンテキスト（マスターメモリ連携）をシームレスに読み込みます。これにより、真にパーソナライズされたマルチユーザー対話を実現し、人・AI・AI同士のクロスプラットフォームなグループ協調をサポートします。

本システムは、一般的なデスクトップPC、組み込みエッジ端末（ESP32）、スマートホーム機器上で動作可能であり、自然言語対話、リアルタイム音声合成・認識、Live2D バーチャルアバター、ワークフロー自動化、ブラウザ操作などを包括し、一人ひとりを深く理解する長期的なエージェント機能を提供します。

中核設計理念：**一般的な家庭用PC1台で動作可能、データは100%ローカル完結。**

主要な3つの柱：**記憶性（あなたを覚えている）、情緒的伴走（生きているような存在感）、拡張性（あらゆる能力を組み込み可能）**。ツールや MCP は基盤インフラであり、目的そのものではありません。

## 主な機能

- **デュアルトラック・メモリシステム** — マスターメモリとプラットフォームユーザーメモリを行レベルで隔離。グループチャット参加者の個別プロファイルトラック（複数グループ間で共有可能）、自動的事実抽出・蒸留、ナレッジベース構築、SQLite による全量ベクトル検索。
- **Live2D バーチャルアバター** — Cubism 5 ランタイム駆動によるリップシンク、表情制御、感情マッピング。PngTuber ドット絵アバターやデスクトップペットモードに対応（VRM サポート計画中）。
- **プラグイン＆スキルシステム** — 動的ホットリロード対応の `CxPlugin` と軽量な `CxSkill` のデュアルトラック拡張。内蔵拡張マーケットとマルチ CDN レジストリに対応。
- **没入型マルチプロバイダー対話** — OpenAI 互換 API（32 テンプレート）、Anthropic ネイティブ、DeepSeek、ローカル Ollama をサポートするマルチターン自然言語対話と SSE ストリーミング。
- **マルチプラットフォーム連携** — 13 種類以上のアダプター（QQ、WeChat、Telegram、Discord、Minecraft、Xiaomi IoT、Home Assistant など）に即時対応。
- **マルチエンジン音声対話** — SherpaOnnx / FunASR / Faster-Whisper による高精度音声認識（ASR）＋ 7 種類の合成エンジン（Edge TTS、SherpaOnnx、ローカル TTS、Gemini、MiniMax、SiliconFlow、Fish Audio）と言語感知フォールバック。
- **標準 MCP ツールプロトコル** — Model Context Protocol（MCP）のネイティブ実装。ツールの登録と呼び出し、CLI・ファイル操作・サブエージェント委譲など 20 以上の内蔵ツールを搭載。
- **マルチエージェント協調＆ A2A** — 課題分析 → サブタスクスケジューリング → 並列実行 → 結果統合。A2A プロトコルによる AI 同士の自律対話をサポート。
- **ビジュアルワークフローエンジン** — ノードベースの視覚的オーケストレーション、テンプレートライブラリ、cron/インターバルスケジューリング（APScheduler）、ツール呼び出し履歴の監査と永続化。
- **安全な組み込みブラウザ** — 外部 DOM 注入リスクを排除した読み取り専用ブラウジング（URL ナビゲーション＋自動スクリーンショット）、収束型 AI ツール（`browser_visit` / `browser_screenshot`）の提供。
- **統合ログセンター** — フロントエンド、メインプロセス、バックエンド、プラットフォームアダプターの 4 系統ログを一元化。リアルタイム閲覧、ログレベル・ソースフィルタリング、個人情報マスク済み診断アップロード。
- **IoT＆スマートホーム連携** — MQTT プロトコル通信、ESP32-P4 ハードウェア端末、Home Assistant（12 デバイスドメイン）および米家（Mijia）の統合デバイス/シーンビュー。
- **Electron デスクトップクライアント** — デスクトップペット、Live2D アバター工房、統合コンソール、アダプティブテーマを備えたデスクトップ環境。
- **コンプライアンス＆セキュリティ保護** — 利用規約とプライバシーポリシーの初回同意ゲート（PIPL、CCPA/CPRA など複数法域対応）、JWT/Token デュアル認証、コマンドサンドボックス、レート制限、AES-256 暗号化設定、24時間自動バックアップ。
- **プライバシー優先** — 対話履歴と記憶データはすべてローカル（単一 SQLite WAL データベース）に保存され、明示的な同意なしに機密情報が外部送信されることはありません。

## 技術スタック

| レイヤー | 採用技術 |
|---------|---------|
| **フロントエンド** | Electron 44 + Vue 3 + TypeScript + Pinia + PixiJS (Live2D Cubism 5) |
| **バックエンド** | Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2 (async) + APScheduler |
| **ストレージ** | SQLite (SQLAlchemy ORM, WAL モード単一 DB) + JSON キャッシュ（PostgreSQL / Redis はクラウド拡張用予約） |
| **通信** | WebSocket + MQTT + HTTP/REST + SSE (Server-Sent Events) |
| **AI / LLM** | OpenAI / Anthropic / DeepSeek / Ollama、マルチベンダーアダプター + パイプラインミドルウェア |
| **音声** | SherpaOnnx / FunASR / Faster-Whisper (ASR) + Edge TTS / 各種クラウド TTS エンジン |
| **ハードウェア** | ESP-IDF (ESP32-P4) |
| **配布/パッケージ** | Docker Compose + PyInstaller + Electron Builder + NSIS |

## クイックスタート

### 前提環境

- Python 3.12+
- Node.js 22+
- pnpm（10.x+ 推奨）

### Make によるワンキー起動

```bash
# リポジトリをクローン
git clone https://github.com/LuminousCX/LuomiNest.git
cd LuomiNest

# 全依存関係のインストール（フロントエンド＋バックエンド）
make install

# 環境変数の初期設定
make config

# バックエンドの起動（ポート 18000）
make dev-backend

# 新しいターミナルを開き、デスクトップクライアントを起動
make dev-frontend
```

### 手動セットアップ

<details>
<summary><strong>バックエンド起動手順</strong></summary>

```bash
cd backend

# 仮想環境の作成と有効化
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 開発用依存関係のインストール
pip install -e ".[dev]"

# 環境変数の設定
cp config/.env.example config/.env
# config/.env を編集し、LLM API キーを設定

# サーバーの起動
python main.py
```

バックエンドはデフォルトで `http://127.0.0.1:18000` で待受を開始します。Swagger API ドキュメントは `http://127.0.0.1:18000/docs` から確認できます。

</details>

<details>
<summary><strong>フロントエンド起動手順</strong></summary>

```bash
cd frontend

# 依存パッケージのインストール
pnpm install

# 開発サーバーおよび Electron の起動
pnpm dev

# 本番ビルド成果物の生成
pnpm build
```

</details>

<details>
<summary><strong>Docker デプロイ</strong></summary>

```bash
cd docker

# 開発環境（backend + PostgreSQL + Redis + MQTT。バックエンドは SQLite を標準使用、pg/redis は予約）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 本番環境
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

</details>

## プロジェクト構成

```
LuomiNest/
├── backend/                     # Python バックエンドサービス
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API エンドポイント（24 モジュール）
│   │   ├── api/ws/              # WebSocket（ブラウザ自動化、アバター制御）
│   │   ├── core/                # 設定、DI、コンテキスト、ワークフロー、エージェント協調
│   │   ├── domains/             # ドメインロジック（ソーシャル、グループ、AI-to-AI 対話）
│   │   ├── engines/             # エンジン（デュアルトラック記憶、音声）
│   │   ├── infrastructure/      # インフラ（28 データベーステーブル、バックアップ、MQTT、アダプター）
│   │   ├── runtime/             # ランタイム（13 プラットフォームアダプター、プラグイン、スキル）
│   │   ├── security/            # セキュリティ（JWT、内部認証、RBAC、サンドボックス、レート制限）
│   │   └── services/            # アプリケーションサービス層
│   ├── config/                  # 環境変数テンプレート
│   ├── plugins/                 # 内蔵プラグイン（4 個）
│   ├── skills/                  # 内蔵軽量スキル（21 個）
│   └── tests/                   # 自動テストスイート
│
├── frontend/                    # Electron + Vue 3 デスクトップクライアント
│   ├── src/
│   │   ├── main/                # Electron メインプロセス（IPC、バックエンドホスティング、ウィンドウ管理）
│   │   ├── preload/             # プリロードスクリプト
│   │   └── renderer/            # Vue 3 レンダラープロセス（24 個の機能ページ）
│   └── resources/               # 静的リソース（アプリアイコン、Live2D モデル）
│
├── firmware/                    # ESP32 組み込みファームウェア
│   └── embedded/esp32-p4/       # ESP32-P4 コントローラー（コンポーネント構成：app / bsp / drivers）
│
├── templates/                   # プラグイン・拡張機能開発テンプレート
└── docker/                      # Docker デプロイ・環境構成
```

## ドキュメントについて

本プロジェクトは包括的な設計・仕様ドキュメント体系（アーキテクチャ、API、データモデル、機能実装、デプロイ、開発ロードマップ）を維持しています。**これらのドキュメントはローカルワークスペース（`文档/` ディレクトリ）内でのみ提供され、公開 Git リポジトリには含まれません**。ローカル環境の該当ディレクトリをご参照ください。

### パッケージングとリリース

デスクトップアプリのローカルビルド、クロスプラットフォーム成果物、GitHub Actions によるリリース手順については、**[frontend/BUILD.md](frontend/BUILD.md)** をご覧ください：
- ローカル一括ビルドスクリプト（`build-all.ps1`）
- GitHub Actions CI/CD（`v*` タグで正式 Release、master ブランチ更新で dev プレリリース自動生成）
- 各プラットフォーム向け成果物（Windows NSIS/ポータブル、Linux AppImage/deb、macOS dmg/zip）およびトラブルシューティング。

## コントリビューション

コミュニティからの貢献を心より歓迎します！参加前に以下のガイドをご確認ください：
- [コントリビューションガイド (Contributing Guide)](CONTRIBUTING_ja.md)
- [行動規範 (Code of Conduct)](CODE_OF_CONDUCT_ja.md)

基本的な参加ステップ：
1. 本リポジトリを Fork
2. フィーチャーブランチを作成：`git checkout -b feature/amazing-feature`
3. 変更をコミット：`git commit -m "feat(scope): add amazing feature"`
4. ブランチをプッシュ：`git push origin feature/amazing-feature`
5. Pull Request を作成

- バグ報告：[バグ報告を送信](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)
- 機能要望：[機能要望を送信](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml)
- コミュニティ討論：[GitHub Discussions](https://github.com/LuminousCX/LuomiNest/discussions)

## セキュリティポリシー

セキュリティ上の脆弱性を発見した場合は、**公開 Issue に投稿しないでください**。以下の宛先へ機密メールとしてご報告ください：

- メールアドレス：`luminouschenxi@outlook.com`
- 件名：`LuomiNest Security Report`

詳細は [セキュリティポリシー (SECURITY.md)](SECURITY_ja.md) を参照してください。

## ライセンス

本プロジェクトは [GNU Affero General Public License v3.0](LICENSE) のもとでオープンソースとして公開されています。

---

<div align="center">

**LuomiNest** by [LuminousCX R&D Team](https://github.com/LuminousCX)

</div>
