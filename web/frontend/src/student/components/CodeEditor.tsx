// v0.96-b: 代码题编辑器 (CodeMirror, python 高亮, 触屏可编辑/工具栏收起)
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { useMemo } from "react";

interface CodeEditorProps {
  value: string;
  onChange: (v: string) => void;
}

export default function CodeEditor({ value, onChange }: CodeEditorProps) {
  const extensions = useMemo(() => [python()], []);
  return (
    <CodeMirror
      value={value}
      height="180px"
      extensions={extensions}
      onChange={onChange}
      basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: false }}
      placeholder="输入代码或答案..."
      className="code-editor"
    />
  );
}
