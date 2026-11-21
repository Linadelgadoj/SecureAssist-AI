import type { ReactNode } from "react";

/**
 * Markdown mínimo para las respuestas del asistente: **negrita**, `código`,
 * listas con viñetas o numeradas, títulos (#) y separadores (---).
 * Construye elementos de React: nunca inserta HTML, así que el texto del
 * modelo no puede inyectar marcado.
 */
function inline(text: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${index++}`;
    if (token.startsWith("**")) parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`")) parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    else parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "ul" | "ol"; items: string[] }
  | { kind: "h"; text: string }
  | { kind: "hr" };

function parse(source: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of source.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const trimmed = line.trim();
    const previous = blocks[blocks.length - 1];
    const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
    const numbered = /^\d+[.)]\s+(.*)$/.exec(trimmed);
    if (!trimmed) { blocks.push({ kind: "p", lines: [] }); continue; }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { blocks.push({ kind: "hr" }); continue; }
    const heading = /^#{1,6}\s+(.*)$/.exec(trimmed);
    if (heading) { blocks.push({ kind: "h", text: heading[1] }); continue; }
    if (bullet || numbered) {
      const kind = bullet ? "ul" : "ol";
      const text = (bullet ?? numbered)![1];
      // Las sublistas indentadas se aplanan en la lista actual.
      if (previous && (previous.kind === "ul" || previous.kind === "ol") && (previous.kind === kind || raw.startsWith(" "))) {
        previous.items.push(text);
      } else {
        blocks.push({ kind, items: [text] });
      }
      continue;
    }
    if (previous?.kind === "p") previous.lines.push(trimmed);
    else blocks.push({ kind: "p", lines: [trimmed] });
  }
  return blocks.filter((block) => block.kind !== "p" || block.lines.length > 0);
}

export function MessageText({ text }: { text: string }) {
  return (
    <div className="message-text">
      {parse(text).map((block, i) => {
        const key = `b${i}`;
        switch (block.kind) {
          case "hr": return <hr key={key} />;
          case "h": return <p key={key} className="message-heading">{inline(block.text, key)}</p>;
          case "ul": return <ul key={key}>{block.items.map((item, j) => <li key={j}>{inline(item, `${key}-${j}`)}</li>)}</ul>;
          case "ol": return <ol key={key}>{block.items.map((item, j) => <li key={j}>{inline(item, `${key}-${j}`)}</li>)}</ol>;
          default: return <p key={key}>{block.lines.map((line, j) => <span key={j}>{j > 0 && <br />}{inline(line, `${key}-${j}`)}</span>)}</p>;
        }
      })}
    </div>
  );
}
