import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import CollapsibleSection from "./CollapsibleSection";

describe("CollapsibleSection", () => {
  it("renders closed by default and includes toggle button", () => {
    const html = renderToStaticMarkup(
      createElement(CollapsibleSection, { title: "测试" }, ""),
    );
    expect(html).toContain("测试");
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain("内容");
  });

  it("renders expanded when defaultExpanded is true", () => {
    const html = renderToStaticMarkup(
      createElement(CollapsibleSection, { title: "测试", defaultExpanded: true }, "内容"),
    );
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("内容");
  });
});
