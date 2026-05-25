"""
slack.py — Sends Slack alerts for new stories with interactive Approve/Reject buttons.
Requires a Slack App with Bot Token scope and an interaction endpoint.

Setup:
  1. Go to api.slack.com/apps → Create New App
  2. Add Bot Token Scopes: chat:write, chat:write.public
  3. Enable Interactivity → set Request URL to http://YOUR_SERVER:3000/slack/actions
  4. Install to workspace → copy Bot Token to .env as SLACK_BOT_TOKEN
  5. Copy Channel ID (right-click channel → View channel details) to SLACK_CHANNEL_ID
  6. Copy Signing Secret from App Credentials to SLACK_SIGNING_SECRET
"""

import os
import json
import hmac
import hashlib
import time
import threading
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


class SlackNotifier:
    def __init__(self):
        self.token = os.getenv("SLACK_BOT_TOKEN", "")
        self.channel = os.getenv("SLACK_CHANNEL_ID", "")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
        self.callback_port = int(os.getenv("SLACK_CALLBACK_PORT", "3000"))
        self._enabled = bool(self.token and self.channel and SLACK_AVAILABLE)
        self._client = WebClient(token=self.token) if self._enabled else None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _content_type_emoji(self, content_type: str) -> str:
        return "⚡" if content_type == "reactive" else "📚"

    def _build_story_blocks(self, story: Dict[str, Any], story_index: int) -> List[Dict]:
        """Build Slack Block Kit blocks for a story alert."""
        title = story.get("topic", "Untitled")
        score = story.get("score", 0)
        content_type = story.get("content_type", "reactive")
        published_at = story.get("published_at", "")
        slug = story.get("slug", "")

        # Sources summary
        sources = story.get("sources", [])
        source_names = [s.get("name", "") for s in sources[:3]]
        sources_str = " · ".join(source_names) if source_names else "Unknown"

        # Additional signals
        hn_source = next((s for s in sources if "Hacker News" in s.get("name", "")), None)
        reddit_source = next((s for s in sources if "Reddit" in s.get("name", "")), None)

        signals = []
        if hn_source:
            signals.append(f"HN: {hn_source.get('hn_score', 0)} pts / {hn_source.get('hn_comments', 0)} comments")
        if reddit_source:
            signals.append(f"Reddit: {reddit_source.get('reddit_score', 0)} upvotes")
        if published_at:
            signals.append(f"Published: {published_at[:16].replace('T', ' ')} UTC")

        signals_str = "  |  ".join(signals) if signals else ""

        # Primary URL
        primary_url = story.get("sources", [{}])[0].get("url", "") if story.get("sources") else ""

        # Images preview
        images = story.get("media", {}).get("images", [])
        has_media = bool(images or story.get("media", {}).get("videos"))

        emoji = self._content_type_emoji(content_type)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Story #{story_index} detected — score {score}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n"
                            f"Type: `{content_type}` | Score: *{score}/100* | Sources: {len(sources)}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Via: {sources_str}"}
                ]
            },
        ]

        if signals_str:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": signals_str}]
            })

        if primary_url:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"<{primary_url}|Read story>"}
            })

        if has_media and images:
            blocks.append({
                "type": "image",
                "image_url": images[0],
                "alt_text": "Story image",
            })

        blocks.append({"type": "divider"})

        # Action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "style": "primary",
                    "value": json.dumps({"action": "approve", "slug": slug}),
                    "action_id": f"approve_{slug}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "style": "danger",
                    "value": json.dumps({"action": "reject", "slug": slug}),
                    "action_id": f"reject_{slug}",
                },
            ]
        })

        return blocks

    def send_story_alert(self, story: Dict[str, Any], story_index: int = 1) -> bool:
        """Send a single story alert to Slack with Approve/Reject buttons."""
        if not self._enabled:
            return False

        blocks = self._build_story_blocks(story, story_index)
        try:
            self._client.chat_postMessage(
                channel=self.channel,
                text=f"New story: {story.get('topic', 'Untitled')} (score {story.get('score', 0)})",
                blocks=blocks,
            )
            return True
        except SlackApiError:
            return False

    def send_watch_summary(
        self,
        stories: List[Dict[str, Any]],
        dashboard_url: str = "http://localhost:5000",
    ) -> bool:
        """
        Send a concise summary ping to Slack when new topics are sourced.
        Format: bell + count + reactive/educational breakdown + dashboard link.
        """
        if not self._enabled:
            return False

        count = len(stories)
        if count == 0:
            return True

        reactive = sum(1 for s in stories if s.get("content_type") == "reactive")
        educational = count - reactive

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🔔 *{count} new topic{'s' if count != 1 else ''} ready for review*\n"
                        f"⚡ {reactive} reactive · 📚 {educational} educational\n\n"
                        f"*Review and approve →* <{dashboard_url}|{dashboard_url}>"
                    ),
                }
            },
        ]

        try:
            self._client.chat_postMessage(
                channel=self.channel,
                text=f"🔔 {count} new topic{'s' if count != 1 else ''} ready for review — {dashboard_url}",
                blocks=blocks,
            )
            return True
        except SlackApiError:
            return False

    def send_daily_summary(self, stories: List[Dict[str, Any]]) -> bool:
        """Send a summary message for the daily buffer batch."""
        if not self._enabled:
            return False

        count = len(stories)
        reactive = sum(1 for s in stories if s.get("content_type") == "reactive")
        educational = count - reactive

        lines = [f"*{s.get('topic', 'Untitled')}* (score {s.get('score', 0)}, {s.get('content_type', '')})"
                 for s in stories[:10]]
        listing = "\n".join(f"  {i+1}. {line}" for i, line in enumerate(lines))

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📋 Daily Buffer Ready", "emoji": True}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{count} topics queued* ({reactive} reactive, {educational} educational)\n\n{listing}"
                }
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "topic.json files saved to outputs/. Run with --interactive to select."}]
            },
        ]

        try:
            self._client.chat_postMessage(
                channel=self.channel,
                text=f"Daily buffer ready: {count} topics queued",
                blocks=blocks,
            )
            return True
        except SlackApiError:
            return False

    def update_message_approved(self, channel: str, ts: str, slug: str, topic: str):
        """Update a Slack message to show it was approved."""
        if not self._enabled:
            return
        try:
            self._client.chat_update(
                channel=channel,
                ts=ts,
                text=f"✅ Approved: {topic}",
                blocks=[{
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✅ *Approved*: {topic}\n`{slug}` queued for Phase 4."}
                }]
            )
        except SlackApiError:
            pass

    def update_message_rejected(self, channel: str, ts: str, slug: str, topic: str):
        """Update a Slack message to show it was rejected."""
        if not self._enabled:
            return
        try:
            self._client.chat_update(
                channel=channel,
                ts=ts,
                text=f"❌ Rejected: {topic}",
                blocks=[{
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"❌ *Rejected*: {topic}\n`{slug}` will not be posted."}
                }]
            )
        except SlackApiError:
            pass


# ── Interaction callback server ───────────────────────────────────────────────

def _verify_slack_signature(signing_secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that a request genuinely came from Slack."""
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def start_interaction_server(notifier: SlackNotifier, outputs_dir: Path, port: int = 3000):
    """
    Start a lightweight Flask server to receive Slack button click callbacks.
    Runs in a background thread so it doesn't block the main process.
    """
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("  [slack] Flask not installed — interactive buttons won't work.")
        print("         Install with: pip install flask")
        return

    app = Flask(__name__)

    @app.route("/slack/actions", methods=["POST"])
    def slack_actions():
        # Verify signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        if notifier.signing_secret:
            if not _verify_slack_signature(notifier.signing_secret, request.get_data(), timestamp, signature):
                return jsonify({"error": "invalid signature"}), 403

        payload = json.loads(request.form.get("payload", "{}"))
        actions = payload.get("actions", [])
        channel = payload.get("channel", {}).get("id", "")
        message_ts = payload.get("message", {}).get("ts", "")

        for action in actions:
            value = json.loads(action.get("value", "{}"))
            action_type = value.get("action")
            slug = value.get("slug", "")

            # Find and update the topic.json file
            topic_files = list(outputs_dir.rglob(f"{slug}/topic.json"))
            topic = slug.replace("-", " ").title()

            if topic_files:
                try:
                    with open(topic_files[0]) as f:
                        data = json.load(f)
                    topic = data.get("topic", topic)
                    data["approved"] = (action_type == "approve")
                    with open(topic_files[0], "w") as f:
                        json.dump(data, f, indent=2)
                except Exception:
                    pass

            if action_type == "approve":
                notifier.update_message_approved(channel, message_ts, slug, topic)
            elif action_type == "reject":
                notifier.update_message_rejected(channel, message_ts, slug, topic)

        return jsonify({"ok": True})

    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    thread.start()
    print(f"  [slack] Interaction server started on port {port}")
