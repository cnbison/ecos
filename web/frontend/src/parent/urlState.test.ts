import { describe, expect, it } from "vitest";
import { isKnownStudent, readStudentParam, studentSearch, STUDENT_QUERY_KEY } from "./urlState";

describe("urlState", () => {
  describe("readStudentParam", () => {
    it("returns the student id from query string", () => {
      expect(readStudentParam("?student=lbc005")).toBe("lbc005");
    });

    it("trims whitespace", () => {
      expect(readStudentParam("?student=%20lbc005%20")).toBe("lbc005");
    });

    it("returns null when key is missing", () => {
      expect(readStudentParam("?other=value")).toBeNull();
    });

    it("returns null when value is empty", () => {
      expect(readStudentParam("?student=")).toBeNull();
      expect(readStudentParam("?student=%20")).toBeNull();
    });
  });

  describe("isKnownStudent", () => {
    const students = [{ student_id: "lbc001" }, { student_id: "lbc002" }];

    it("returns true for known id", () => {
      expect(isKnownStudent("lbc001", students)).toBe(true);
    });

    it("returns false for unknown id", () => {
      expect(isKnownStudent("lbc999", students)).toBe(false);
    });

    it("returns false for null", () => {
      expect(isKnownStudent(null, students)).toBe(false);
    });

    it("returns false for empty list", () => {
      expect(isKnownStudent("lbc001", [])).toBe(false);
    });
  });

  describe("studentSearch", () => {
    it("returns query object with student key", () => {
      expect(studentSearch("lbc005")).toEqual({ [STUDENT_QUERY_KEY]: "lbc005" });
    });

    it("returns empty object when id is null", () => {
      expect(studentSearch(null)).toEqual({});
    });
  });
});
