import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

const { fontFamily: interFamily } = loadInter();

/**
 * ChatScene — animated Claude.ai conversation.
 *
 * Re-stages a chat transcript as a live UI: user types into the input, presses
 * send, the bubble springs up, Claude shows a "thinking" pulse, then streams its
 * reply token-by-token. Old turns scroll up as new ones come in.
 *
 * The skin is parameterised by `app` so the same component handles ChatGPT and
 * Gemini styles in future runs.
 */

export type ChatTurn = {
  role: "user" | "assistant";
  text: string;
  /** Optional thinking/header line shown above an assistant turn (the small
   *  italic preview line in Claude's UI, e.g. "Reconsidered output…"). */
  thinking?: string;
};

export type ChatApp = "claude" | "chatgpt" | "gemini";

type Props = {
  app: ChatApp;
  /** Conversation to play. Must alternate user/assistant. */
  turns: ChatTurn[];
  /** Footer label, e.g. "Sonnet 4.5  Extended". Defaults per-app. */
  modelLabel?: string;
  accentColor: string;
  /** Optional ambient backdrop (typically a Pexels b-roll clip).
   *  Renders blurred + dimmed under the desktop chat window. When
   *  omitted, falls back to the radial-gradient backdrop. */
  bgMediaSrc?: string;
};

/* ── Theme ───────────────────────────────────────────────────────────────── */

type Theme = {
  bg: string;
  text: string;
  meta: string;
  userBubble: string;
  userText: string;
  inputBg: string;
  inputBorder: string;
  inputPlaceholder: string;
  sendBg: string;
  sendIcon: string;
  thinkingText: string;
  fontStack: string;
};

const THEMES: Record<ChatApp, Theme> = {
  claude: {
    bg: "#262624",
    text: "#F5F4ED",
    meta: "#A8A6A0",
    userBubble: "#3A3936",
    userText: "#F5F4ED",
    inputBg: "#30302D",
    inputBorder: "#3A3936",
    inputPlaceholder: "#9A9892",
    sendBg: "#C66B47",
    sendIcon: "#1A1916",
    thinkingText: "#A8A6A0",
    fontStack: `"Inter", ${interFamily}, system-ui, sans-serif`,
  },
  chatgpt: {
    bg: "#212121",
    text: "#ECECEC",
    meta: "#8E8EA0",
    userBubble: "#2F2F2F",
    userText: "#ECECEC",
    inputBg: "#2F2F2F",
    inputBorder: "#3A3A3A",
    inputPlaceholder: "#8E8EA0",
    sendBg: "#FFFFFF",
    sendIcon: "#000000",
    thinkingText: "#8E8EA0",
    fontStack: `"Inter", ${interFamily}, system-ui, sans-serif`,
  },
  gemini: {
    bg: "#1B1C1D",
    text: "#E3E3E3",
    meta: "#9AA0A6",
    userBubble: "#2D2E30",
    userText: "#E3E3E3",
    inputBg: "#2D2E30",
    inputBorder: "#3C4043",
    inputPlaceholder: "#9AA0A6",
    sendBg: "#8AB4F8",
    sendIcon: "#1B1C1D",
    thinkingText: "#9AA0A6",
    fontStack: `"Inter", ${interFamily}, system-ui, sans-serif`,
  },
};

const DEFAULT_MODEL_LABEL: Record<ChatApp, string> = {
  claude: "Sonnet 4.5  Extended",
  chatgpt: "GPT-4o",
  gemini: "2.5 Pro",
};

/* ── Timing ──────────────────────────────────────────────────────────────── */

// All frames @ 30fps. Keep these in sync with
// content_gen/script_agent/_build_chat_script.py and the script-agent
// scene-writer prompt.
const TYPE_CHARS_PER_SEC = 32;       // user typing into input
const SEND_SPRING_FRAMES = 8;        // bubble fly from input → top
const THINKING_FRAMES = 12;          // pulse before Claude streams
const STREAM_CHARS_PER_SEC = 65;     // Claude streaming back (readable)
const POST_TURN_PAUSE_FRAMES = 14;   // beat after each turn

type TurnTiming = {
  /** Frame at which this turn starts being authored. */
  start: number;
  /** Frame at which this turn is fully on-screen. */
  end: number;
  /** For users: when typing finishes (pre-send). */
  typeEnd?: number;
  /** For users: when the bubble has finished flying up. */
  sendEnd?: number;
  /** For assistants: when the thinking pulse ends. */
  thinkingEnd?: number;
  /** Char count at which streaming completes. */
  fullChars: number;
};

function planTimings(turns: ChatTurn[], fps: number): TurnTiming[] {
  const timings: TurnTiming[] = [];
  let cursor = 6; // small lead-in pause
  for (const turn of turns) {
    const charCount = turn.text.length;
    if (turn.role === "user") {
      const typeFrames = Math.max(8, Math.round((charCount / TYPE_CHARS_PER_SEC) * fps));
      const start = cursor;
      const typeEnd = start + typeFrames;
      const sendEnd = typeEnd + SEND_SPRING_FRAMES;
      const end = sendEnd + POST_TURN_PAUSE_FRAMES;
      timings.push({ start, end, typeEnd, sendEnd, fullChars: charCount });
      cursor = end;
    } else {
      const streamFrames = Math.max(10, Math.round((charCount / STREAM_CHARS_PER_SEC) * fps));
      const start = cursor;
      const thinkingEnd = start + THINKING_FRAMES;
      const end = thinkingEnd + streamFrames + POST_TURN_PAUSE_FRAMES;
      timings.push({ start, end, thinkingEnd, fullChars: charCount });
      cursor = end;
    }
  }
  return timings;
}

/* ── Markdown-ish renderer ───────────────────────────────────────────────── */
/**
 * Render a string that may contain bold (**foo**), bullet lists (lines
 * starting with "- " or "• "), numbered lists, and red-blocked words like
 * `[REDACTED]` or `[FU██]` → painted red. We accept a `revealedChars` count
 * to clip mid-stream.
 */
function renderRichText(
  fullText: string,
  revealedChars: number,
  theme: Theme,
  options: { fontSize: number }
): React.ReactNode {
  const truncated = fullText.slice(0, Math.max(0, Math.floor(revealedChars)));
  const lines = truncated.split("\n");

  const elements: React.ReactNode[] = [];
  let inList: null | "bullet" | "number" = null;
  let listBuffer: React.ReactNode[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    if (inList === "bullet") {
      elements.push(
        <ul
          key={key}
          style={{
            margin: "8px 0",
            paddingLeft: 32,
            listStyleType: "disc",
            listStylePosition: "outside",
          }}
        >
          {listBuffer}
        </ul>
      );
    } else if (inList === "number") {
      elements.push(
        <ol
          key={key}
          style={{
            margin: "8px 0",
            paddingLeft: 32,
            listStyleType: "decimal",
            listStylePosition: "outside",
          }}
        >
          {listBuffer}
        </ol>
      );
    }
    listBuffer = [];
    inList = null;
  };

  lines.forEach((rawLine, i) => {
    const line = rawLine.replace(/\s+$/, "");

    const bullet = line.match(/^\s*[-•]\s+(.*)$/);
    const numbered = line.match(/^\s*(\d+)\.\s+(.*)$/);

    if (bullet) {
      if (inList && inList !== "bullet") flushList(`flush-${i}`);
      inList = "bullet";
      listBuffer.push(
        <li key={`li-${i}`} style={{ margin: "4px 0", lineHeight: 1.45 }}>
          {renderInline(bullet[1], theme)}
        </li>
      );
      return;
    }
    if (numbered) {
      if (inList && inList !== "number") flushList(`flush-${i}`);
      inList = "number";
      listBuffer.push(
        <li key={`li-${i}`} style={{ margin: "4px 0", lineHeight: 1.45 }}>
          {renderInline(numbered[2], theme)}
        </li>
      );
      return;
    }

    if (inList) flushList(`flush-${i}`);

    if (line.trim() === "") {
      elements.push(<div key={`spacer-${i}`} style={{ height: options.fontSize * 0.6 }} />);
      return;
    }

    // Section header: line ending with ":" and entirely bold-ish (we treat
    // them as bold by default since Claude's UI does the same).
    const isHeader = /^[A-Z][^.]*:\s*$/.test(line.trim()) || /^\*\*[^*]+\*\*:?\s*$/.test(line.trim());
    elements.push(
      <p
        key={`p-${i}`}
        style={{
          margin: "8px 0",
          lineHeight: 1.45,
          fontWeight: isHeader ? 700 : 400,
        }}
      >
        {renderInline(line, theme)}
      </p>
    );
  });

  if (inList) flushList("flush-final");
  return elements;
}

/** Render inline markup: `**bold**` and `[REDACTED text]` red blocks. */
function renderInline(text: string, theme: Theme): React.ReactNode {
  // Split on **...** keeping bold runs.
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[REDACTED[^\]]*\]|\[[^\]]*\u2588[^\]]*\])/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(
        <strong key={key++} style={{ fontWeight: 700 }}>
          {tok.slice(2, -2)}
        </strong>
      );
    } else {
      // [REDACTED ...] or [██] block
      parts.push(
        <span
          key={key++}
          style={{
            display: "inline-block",
            background: "#E94B3C",
            color: "transparent",
            padding: "0 12px",
            borderRadius: 4,
            verticalAlign: "middle",
            height: "0.95em",
            minWidth: 56,
          }}
        >
          {tok}
        </span>
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(<span key={key++}>{text.slice(last)}</span>);
  return parts;
}

/* ── ChatScene component ─────────────────────────────────────────────────── */

export const ChatScene: React.FC<Props> = ({
  app,
  turns,
  modelLabel,
  accentColor: _accentColor,
  bgMediaSrc,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const theme = THEMES[app];

  const timings = planTimings(turns, fps);

  // ── DESKTOP WINDOW LAYOUT ────────────────────────────────────────────
  // The chat now renders inside a fake macOS-style desktop window that is
  // top-anchored to the canvas at a horizontal aspect (1080×720, ~3:2).
  // Below the window, the rest of the 9:16 canvas (y=720 → y=1920) is a
  // soft gradient backdrop. This way the desktop UI keeps its NATURAL
  // landscape proportions instead of being stretched to fill 9:16.
  const CHAT_WIN_W = width;       // 1080 — same as canvas width
  const CHAT_WIN_H = 720;         // ≈3:2 desktop aspect
  const SIDEBAR_W = 240;
  const TITLE_BAR_H = 44;         // mac window-control strip
  const TOP_CHROME_H = 60;        // chat-title bar inside the window
  const PAD_X = 28;               // padding inside the main chat panel
  const TOP_INSET = TITLE_BAR_H + TOP_CHROME_H;
  const INPUT_HEIGHT = 140;
  const INPUT_BOTTOM_INSET = 24;
  const TURN_GAP = 22;
  const FONT_SIZE = 26;

  const mainLeft = SIDEBAR_W;
  const mainRight = 0;
  const mainWidth = CHAT_WIN_W - mainLeft - mainRight;

  // All transcript / input geometry is RELATIVE to the chat window, not
  // the canvas. The chat window itself is parented under an absolute div
  // at (0, 0, 1080, 720) further below.
  const transcriptTop = TOP_INSET + 12;
  const transcriptBottom = CHAT_WIN_H - INPUT_HEIGHT - INPUT_BOTTOM_INSET - 16;
  const transcriptHeight = transcriptBottom - transcriptTop;

  /* ── Compute current input value (what's in the textbox right now) ────── */

  let inputValue = "";
  let activeUserTiming: TurnTiming | null = null;
  let pendingSendBubble: { text: string; t: number } | null = null;

  for (let i = 0; i < turns.length; i++) {
    const turn = turns[i];
    const t = timings[i];
    if (turn.role !== "user") continue;
    if (frame >= t.start && frame < (t.typeEnd ?? t.end)) {
      // Typing phase
      const local = frame - t.start;
      const totalTypeFrames = (t.typeEnd ?? t.start) - t.start;
      const charsRevealed = Math.floor((local / Math.max(1, totalTypeFrames)) * turn.text.length);
      inputValue = turn.text.slice(0, charsRevealed);
      activeUserTiming = t;
      break;
    }
    if (frame >= (t.typeEnd ?? t.start) && frame < (t.sendEnd ?? t.end)) {
      // Send animation phase: bubble flying up from input area
      const sendStart = t.typeEnd ?? t.start;
      const sendDur = (t.sendEnd ?? t.start) - sendStart;
      const localFrame = frame - sendStart;
      pendingSendBubble = { text: turn.text, t: localFrame / Math.max(1, sendDur) };
      activeUserTiming = t;
      break;
    }
  }

  /* ── Build the static transcript (turns already "delivered") ──────────── */
  // A turn is considered "delivered" as soon as its sendEnd / thinkingEnd has
  // passed (for users) or its full streaming progress is well under way (for
  // assistants — we render them in-place with a streaming reveal).

  type RenderedTurn = {
    index: number;
    role: "user" | "assistant";
    node: React.ReactNode;
  };

  const renderedTurns: RenderedTurn[] = [];

  for (let i = 0; i < turns.length; i++) {
    const turn = turns[i];
    const t = timings[i];

    if (turn.role === "user") {
      if (frame < (t.sendEnd ?? t.end)) continue; // not yet pinned to the top-right
      // Spring-in completion factor for the freshly-pinned bubble
      const sinceLanded = Math.max(0, frame - (t.sendEnd ?? t.end));
      const settle = spring({
        frame: sinceLanded,
        fps,
        config: { damping: 18, stiffness: 220, mass: 0.6 },
      });
      renderedTurns.push({
        index: i,
        role: "user",
        node: (
          <div
            style={{
              alignSelf: "flex-end",
              maxWidth: "78%",
              background: theme.userBubble,
              color: theme.userText,
              padding: "16px 22px",
              borderRadius: 22,
              fontSize: FONT_SIZE,
              fontFamily: theme.fontStack,
              fontWeight: 500,
              lineHeight: 1.35,
              transform: `translateY(${(1 - settle) * 8}px)`,
            }}
          >
            {turn.text}
          </div>
        ),
      });
    } else {
      // Assistant turn: starts rendering after thinking pulse ends.
      const thinkingEnd = t.thinkingEnd ?? t.start + THINKING_FRAMES;
      if (frame < t.start) continue;
      const showThinking = frame < thinkingEnd;
      const streamProgress = showThinking
        ? 0
        : Math.min(1, (frame - thinkingEnd) / Math.max(1, (t.end - POST_TURN_PAUSE_FRAMES) - thinkingEnd));
      const revealedChars = streamProgress * turn.text.length;

      renderedTurns.push({
        index: i,
        role: "assistant",
        node: (
          <div
            style={{
              alignSelf: "flex-start",
              width: "100%",
              color: theme.text,
              fontSize: FONT_SIZE,
              fontFamily: theme.fontStack,
              fontWeight: 400,
              lineHeight: 1.45,
            }}
          >
            {turn.thinking ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  color: theme.thinkingText,
                  fontSize: FONT_SIZE * 0.78,
                  marginBottom: 14,
                  opacity: showThinking ? 0.55 + 0.45 * Math.sin(frame / 4) * 0.5 : 1,
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    border: `2px solid ${theme.meta}`,
                    borderTopColor: "transparent",
                    transform: `rotate(${frame * 12}deg)`,
                  }}
                />
                <span>{turn.thinking}</span>
                <span style={{ opacity: 0.6 }}>›</span>
              </div>
            ) : null}
            {showThinking ? (
              <div style={{ display: "flex", gap: 10, padding: "12px 0", color: theme.meta }}>
                {[0, 1, 2].map((dot) => {
                  const t0 = frame * 0.35 - dot * 1.6;
                  const a = 0.35 + 0.65 * (Math.sin(t0) * 0.5 + 0.5);
                  return (
                    <span
                      key={dot}
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        background: theme.meta,
                        opacity: a,
                      }}
                    />
                  );
                })}
              </div>
            ) : (
              <div style={{ position: "relative" }}>
                {renderRichText(turn.text, revealedChars, theme, { fontSize: FONT_SIZE })}
                {streamProgress < 1 ? (
                  <span
                    style={{
                      display: "inline-block",
                      width: 14,
                      height: FONT_SIZE * 0.95,
                      verticalAlign: "text-bottom",
                      background: theme.text,
                      opacity: Math.sin(frame / 3) * 0.5 + 0.5,
                      marginLeft: 4,
                    }}
                  />
                ) : null}
              </div>
            )}
          </div>
        ),
      });
    }
  }

  // Compute scroll offset so the bottom of the transcript is glued to the
  // bottom of the visible area. We measure heights at runtime via a flex
  // column and translate the entire stack upward by an estimated amount,
  // approximated from how much content has been delivered.
  // Rough estimate: pixels per turn — we do a content-aware estimate below.
  const turnsRendered = renderedTurns.length;
  // Approximate height per turn so old content scrolls off as we exceed the
  // viewport. (The real overflow is hidden; this is purely the scroll-up
  // animation that mimics Claude's auto-scroll behavior.)
  const APPROX_USER_TURN_PX = 130;
  const APPROX_ASSISTANT_LINE_PX = FONT_SIZE * 1.55;
  const approxHeights = renderedTurns.map((rt) => {
    const turn = turns[rt.index];
    if (turn.role === "user") return APPROX_USER_TURN_PX;
    const lines = Math.max(2, Math.ceil(turn.text.length / 60));
    return lines * APPROX_ASSISTANT_LINE_PX + (turn.thinking ? FONT_SIZE * 1.1 : 0) + 24;
  });
  const totalApprox = approxHeights.reduce((a, b) => a + b, 0) + Math.max(0, turnsRendered - 1) * TURN_GAP;
  const overflow = Math.max(0, totalApprox - transcriptHeight);
  const scrollY = -overflow;

  /* ── The flying-send bubble (between input and final pinned position) ── */

  let flyingBubble: React.ReactNode = null;
  if (pendingSendBubble && activeUserTiming) {
    const t = pendingSendBubble.t;
    const eased = 1 - Math.pow(1 - t, 3);
    const startY = CHAT_WIN_H - INPUT_HEIGHT - INPUT_BOTTOM_INSET + 20; // near input
    const endY = transcriptTop + 20; // top of transcript area, on the right
    const y = startY + (endY - startY) * eased;
    flyingBubble = (
      <div
        style={{
          position: "absolute",
          right: PAD_X,
          top: y,
          maxWidth: "78%",
          background: theme.userBubble,
          color: theme.userText,
          padding: "14px 20px",
          borderRadius: 18,
          fontSize: FONT_SIZE,
          fontFamily: theme.fontStack,
          fontWeight: 500,
          lineHeight: 1.35,
          transform: `scale(${0.92 + 0.08 * eased})`,
          opacity: 1 - 0.15 * (1 - eased),
        }}
      >
        {pendingSendBubble.text}
      </div>
    );
  }

  /* ── Desktop window: title bar + sidebar ─────────────────────────────── */

  // Slightly darker than the main chat bg so the sidebar reads as separate.
  const sidebarBg =
    app === "claude" ? "#1F1E1C" : app === "chatgpt" ? "#181818" : "#161718";
  const dotColors = ["#FF5F57", "#FEBC2E", "#28C840"];
  const fakeChatTitles =
    app === "claude"
      ? [
          "Building documentary workflow",
          "Editing prompts for safety",
          "Memorai system architecture",
          "Refactoring scene writer",
        ]
      : [
          "Plan the launch deck",
          "Refactor the data pipeline",
          "Review agent transcripts",
          "Compare model latencies",
        ];

  const TitleBar = (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: TITLE_BAR_H,
        background: "#0F0E0D",
        borderBottom: `1px solid ${theme.inputBorder}`,
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "0 22px",
        zIndex: 5,
      }}
    >
      {dotColors.map((c) => (
        <span
          key={c}
          style={{
            display: "inline-block",
            width: 14,
            height: 14,
            borderRadius: "50%",
            background: c,
          }}
        />
      ))}
      <div style={{ flex: 1 }} />
      <span style={{ color: theme.meta, fontSize: 22, opacity: 0.6 }}>
        {app === "claude"
          ? "claude.ai"
          : app === "chatgpt"
          ? "chat.openai.com"
          : "gemini.google.com"}
      </span>
      <div style={{ flex: 1 }} />
    </div>
  );

  const Sidebar = (
    <div
      style={{
        position: "absolute",
        top: TITLE_BAR_H,
        left: 0,
        bottom: 0,
        width: SIDEBAR_W,
        background: sidebarBg,
        borderRight: `1px solid ${theme.inputBorder}`,
        padding: "20px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        fontFamily: theme.fontStack,
        zIndex: 4,
      }}
    >
      {/* Logo */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 6,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: theme.sendBg,
            color: theme.sendIcon,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 900,
            fontSize: 22,
          }}
        >
          {app === "claude" ? "✦" : app === "chatgpt" ? "◉" : "G"}
        </div>
        <span style={{ color: theme.text, fontSize: 22, fontWeight: 600 }}>
          {app === "claude" ? "Claude" : app === "chatgpt" ? "ChatGPT" : "Gemini"}
        </span>
      </div>

      {/* New chat button */}
      <div
        style={{
          background: theme.inputBg,
          border: `1px solid ${theme.inputBorder}`,
          borderRadius: 10,
          color: theme.text,
          fontSize: 18,
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span style={{ fontSize: 20, color: theme.meta }}>+</span>
        New chat
      </div>

      {/* Search */}
      <div
        style={{
          background: theme.inputBg,
          border: `1px solid ${theme.inputBorder}`,
          borderRadius: 10,
          color: theme.inputPlaceholder,
          fontSize: 18,
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span style={{ fontSize: 18 }}>⌕</span>
        Search
      </div>

      {/* Sections */}
      <div style={{ marginTop: 8, color: theme.meta, fontSize: 14, fontWeight: 700, letterSpacing: 1 }}>
        RECENTS
      </div>
      {fakeChatTitles.map((title, i) => (
        <div
          key={i}
          style={{
            color: i === 0 ? theme.text : theme.meta,
            fontSize: 17,
            padding: "8px 12px",
            borderRadius: 8,
            background: i === 0 ? theme.userBubble : "transparent",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {title}
        </div>
      ))}

      <div style={{ flex: 1 }} />

      {/* User avatar at bottom */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 8px",
          borderTop: `1px solid ${theme.inputBorder}`,
          paddingTop: 14,
        }}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: "50%",
            background: theme.sendBg,
          }}
        />
        <span style={{ color: theme.text, fontSize: 16 }}>Free plan</span>
      </div>
    </div>
  );

  const ChatTitleBar = (
    <div
      style={{
        position: "absolute",
        top: TITLE_BAR_H,
        left: SIDEBAR_W,
        right: 0,
        height: TOP_CHROME_H,
        borderBottom: `1px solid ${theme.inputBorder}`,
        display: "flex",
        alignItems: "center",
        padding: "0 28px",
        gap: 14,
        background: theme.bg,
        zIndex: 3,
      }}
    >
      <span style={{ color: theme.text, fontSize: 22, fontWeight: 600 }}>
        {turns.length > 0 ? turns[0].text.slice(0, 56) : "New conversation"}
      </span>
      <div style={{ flex: 1 }} />
      <span style={{ color: theme.meta, fontSize: 18 }}>
        {modelLabel ?? DEFAULT_MODEL_LABEL[app]}
      </span>
      <span
        style={{
          color: theme.meta,
          fontSize: 24,
          opacity: 0.6,
        }}
      >
        ⋯
      </span>
    </div>
  );

  /* ── Input box ─────────────────────────────────────────────────────────── */
  // Hide the input value (and hide the cursor) once the user-bubble has been
  // sent, until the next user turn begins typing.
  const showCaret =
    activeUserTiming != null &&
    frame >= activeUserTiming.start &&
    frame < (activeUserTiming.typeEnd ?? activeUserTiming.start);

  const InputBox = (
    <div
      style={{
        position: "absolute",
        left: mainLeft + PAD_X,
        right: PAD_X,
        bottom: INPUT_BOTTOM_INSET,
        height: INPUT_HEIGHT - 20,
        background: theme.inputBg,
        border: `1px solid ${theme.inputBorder}`,
        borderRadius: 22,
        padding: "22px 24px 18px 24px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        fontFamily: theme.fontStack,
      }}
    >
      <div
        style={{
          color: inputValue ? theme.text : theme.inputPlaceholder,
          fontSize: FONT_SIZE,
          lineHeight: 1.3,
          fontWeight: 400,
          minHeight: FONT_SIZE * 1.3,
        }}
      >
        {inputValue || "Reply..."}
        {showCaret ? (
          <span
            style={{
              display: "inline-block",
              width: 3,
              height: FONT_SIZE * 0.9,
              background: theme.text,
              marginLeft: 4,
              verticalAlign: "text-bottom",
              opacity: Math.floor(frame / 8) % 2 === 0 ? 1 : 0,
            }}
          />
        ) : null}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginTop: 12,
          color: theme.meta,
          fontSize: FONT_SIZE * 0.7,
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            border: `2px solid ${theme.meta}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: theme.meta,
          }}
        >
          +
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <span>{modelLabel ?? DEFAULT_MODEL_LABEL[app]}</span>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: theme.sendBg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 30,
            color: theme.sendIcon,
            fontWeight: 700,
          }}
          >
            ↑
          </div>
        </div>
      </div>
    </div>
  );

  /* ── Compose ───────────────────────────────────────────────────────────── */

  /* ── Compose: canvas backdrop + top-anchored desktop window ──────────── */

  const resolveBg = (src: string): string => {
    if (
      src.startsWith("data:") ||
      src.startsWith("http://") ||
      src.startsWith("https://") ||
      src.startsWith("/")
    ) {
      return src;
    }
    return staticFile(src);
  };
  const isVideoBg = (src: string): boolean => {
    const lowered = src.split("?")[0].toLowerCase();
    if (lowered.startsWith("data:video/")) return true;
    return /\.(mp4|webm|mov|m4v)$/.test(lowered);
  };

  const canvasBackdrop = bgMediaSrc ? (
    // Pexels b-roll backdrop — full-bleed cover (no blur, no saturate boost
    // per the no-glow rule) + solid scrim for legibility.
    <>
      <AbsoluteFill>
        {isVideoBg(bgMediaSrc) ? (
          <OffthreadVideo
            src={resolveBg(bgMediaSrc)}
            muted
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          <Img
            src={resolveBg(bgMediaSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "rgba(0,0,0,0.55)" }} />
    </>
  ) : (
    // Fallback: solid dark backdrop. No radial wash, no blurred glow patch.
    <AbsoluteFill style={{ background: "#0a0a0a" }} />
  );

  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      {canvasBackdrop}

      {/* (Drop shadow under the desktop window removed — flat per no-glow rule.) */}

      {/* Desktop window itself — top-anchored, 1080×720 (≈3:2). Internal
          coordinates (TitleBar / Sidebar / ChatTitleBar / InputBox) are
          all RELATIVE to this window, not the canvas. */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: CHAT_WIN_W,
          height: CHAT_WIN_H,
          background: theme.bg,
          overflow: "hidden",
          fontFamily: theme.fontStack,
          borderBottomLeftRadius: 18,
          borderBottomRightRadius: 18,
        }}
      >
        {TitleBar}
        {Sidebar}
        {ChatTitleBar}

        {/* Transcript pane — sits in the right column (after sidebar),
            bottom-anchored, scrolls up as content fills it. */}
        <div
          style={{
            position: "absolute",
            left: mainLeft + PAD_X,
            right: PAD_X,
            top: transcriptTop,
            height: transcriptHeight,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: TURN_GAP,
              color: theme.text,
              transform: `translateY(${scrollY}px)`,
            }}
          >
            {renderedTurns.map((rt) => (
              <div
                key={rt.index}
                style={{
                  display: "flex",
                  width: "100%",
                  justifyContent: rt.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                {rt.node}
              </div>
            ))}
          </div>
        </div>

        {flyingBubble}

        {InputBox}

        {/* Solid top mask so the chat title bar stays readable when transcript
            grows under it (was a fade gradient; now a flat tint matching the
            window bg). */}
        <div
          style={{
            position: "absolute",
            top: TITLE_BAR_H + TOP_CHROME_H,
            left: mainLeft,
            right: 0,
            height: 24,
            background: theme.bg,
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Reference unused props for ESLint */}
      <span style={{ display: "none" }}>
        {_accentColor ? "" : ""}
        {mainWidth ? "" : ""}
        {height ? "" : ""}
      </span>
    </AbsoluteFill>
  );
};

/* ── Helper: minimum scene duration for a turn list ──────────────────────── */
/**
 * Given a list of turns, return the minimum total seconds the ChatScene
 * needs to play through them. The script agent uses this to size scene
 * duration so nothing gets cut mid-stream.
 */
export function computeChatSceneDuration(turns: ChatTurn[], fps = 30): number {
  const t = planTimings(turns, fps);
  if (t.length === 0) return 1;
  return (t[t.length - 1].end + 12) / fps;
}
