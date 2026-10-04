import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Circle,
  FileText,
  Mic,
  VolumeX,
  Volume2,
  ArrowUpRight,
} from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { IconButton } from "./Controls";
import { VoiceOrb } from "./VoiceOrb";
import { orbSpring } from "../animations";
export function FloatingAssistant() {
  const [expanded, setExpanded] = useState(false);
  const question = useApp((s) => s.data?.question);
  const status = useMedia((s) => s.status);
  const gesture = useRef({ x: 0, y: 0, moved: false, down: false });
  useEffect(() => {
    document.body.classList.add("overlay-body");
    document.documentElement.style.background = "transparent";
    return () => document.body.classList.remove("overlay-body");
  }, []);
  useEffect(() => {
    if (expanded || question) void window.desktop.overlay(expanded, !!question);
    else {
      const timer = setTimeout(
        () => void window.desktop.overlay(false, false),
        260,
      );
      return () => clearTimeout(timer);
    }
  }, [expanded, question]);
  const actions = [
    {
      label: status.state === "recording" ? "Stop recording" : "Record",
      action: "record",
      Icon: Circle,
    },
    { label: "Context", action: "context", Icon: FileText },
    {
      label: status.voice === "listening" ? "Finish answer" : "Voice answer",
      action: "voice",
      Icon: Mic,
    },
    {
      label: status.muted ? "Unmute assistant" : "Mute assistant",
      action: "mute",
      Icon: status.muted ? VolumeX : Volume2,
    },
    { label: "Open app", action: "open", Icon: ArrowUpRight },
  ];
  return (
    <div
      className="overlay-stage"
      onPointerMove={(event) => {
        const target = event.target as HTMLElement;
        void window.desktop.passthrough(
          !gesture.current.down && !target.closest("[data-interactive]"),
        );
      }}
    >
      <AnimatePresence>
        {question && (
          <motion.div
            data-interactive
            className="orb-question"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96 }}
          >
            <span className="eyebrow">AI ASSISTANT</span>
            <p>{question.text}</p>
            <div className="button-row">
              <ButtonSmall text="Answer" action="voice" />
              <ButtonSmall text="Type instead" action="context" />
              <button
                onClick={() => run(() => useApp.getState().command("defer"))}
              >
                Later
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <motion.div
        data-interactive
        layout
        transition={orbSpring}
        className={`orb-toolbar ${expanded ? "expanded" : ""}`}
      >
        <AnimatePresence>
          {expanded && (
            <motion.div
              className="orb-actions"
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
            >
              {actions.map(({ label, action, Icon }, index) => (
                <motion.div
                  key={action}
                  initial={{ opacity: 0, scale: 0.92 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: index * 0.025, duration: 0.14 }}
                >
                  <IconButton
                    label={label}
                    onClick={() => run(() => window.desktop.relay(action))}
                  >
                    <Icon
                      size={17}
                      className={action === "record" ? "red" : ""}
                    />
                  </IconButton>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        <button
          className="orb-handle"
          aria-label={expanded ? "Collapse assistant" : "Expand assistant"}
          onPointerDown={(e) => {
            gesture.current = {
              x: e.screenX,
              y: e.screenY,
              moved: false,
              down: true,
            };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const g = gesture.current;
            if (!g.down) return;
            const dx = e.screenX - g.x,
              dy = e.screenY - g.y;
            if (g.moved || Math.abs(dx) + Math.abs(dy) > 5) {
              g.moved = true;
              g.x = e.screenX;
              g.y = e.screenY;
              void window.desktop.drag(dx, dy);
            }
          }}
          onPointerUp={() => {
            gesture.current.down = false;
            if (!gesture.current.moved) setExpanded(!expanded);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setExpanded(!expanded);
            }
          }}
        >
          <VoiceOrb
            active={["listening", "speaking"].includes(status.voice)}
            muted={status.muted}
            recording={status.state === "recording"}
          />
        </button>
      </motion.div>
    </div>
  );
}
function ButtonSmall({ text, action }: { text: string; action: string }) {
  return (
    <button onClick={() => run(() => window.desktop.relay(action))}>
      {text}
    </button>
  );
}
