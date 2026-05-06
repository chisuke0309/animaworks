# MEMORY.md — animaworks プロジェクト経験記録

---

## X事業部 運用終了（2026-05-01）

**決定**: ペットケアコンテンツのX自動投稿運用を終了。

**理由**: 約6週間稼働、フォロワー9名止まり。継続の費用対効果なしとchisuke判断。

**存続する資産（コードはすべて保持）**:
- 自動X投稿パイプライン（`core/tools/x_post.py`）
- ニッチ調査・ハッシュタグリサーチ（rue anima）
- コンテンツ生成テンプレート（kuro anima）
- 画像生成連携（sora anima）

**再開方法**:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.animaworks.server.plist
```

**停止方法（再停止時）**:
```bash
launchctl bootout gui/$(id -u)/com.animaworks.server
launchctl disable gui/$(id -u)/com.animaworks.server
```

→ 活用方法は別途検討予定（時期未定）

---

## AnimaWorksサーバー管理

- **LaunchAgent**: `~/Library/LaunchAgents/com.animaworks.server.plist`
- **サービス名**: `com.animaworks.server`
- **再起動**: `launchctl kickstart -k gui/$(id -u)/com.animaworks.server`
- **現在の状態**: 停止・自動起動無効（2026-05-01時点）
