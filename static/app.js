(() => {
  "use strict";

  const form = document.querySelector("#query-form");
  const questionInput = document.querySelector("#question");
  const submitButton = document.querySelector("#submit-button");
  const statusMessage = document.querySelector("#status-message");
  const resultPanel = document.querySelector("#result-panel");
  const sqlOutput = document.querySelector("#sql-output");
  const rowCount = document.querySelector("#row-count");
  const tableContainer = document.querySelector("#table-container");
  const truncatedMessage = document.querySelector("#truncated-message");
  const historyList = document.querySelector("#history-list");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = questionInput.value.trim();
    if (!question) {
      showStatus("Enter a question to get started.", "error");
      questionInput.focus();
      return;
    }

    setLoading(true);
    resultPanel.hidden = true;
    showStatus("Generating and validating a read-only query…", "loading");
    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ question }),
      });
      const payload = await response.json();
      if (!response.ok) {
        if (payload.sql) {
          sqlOutput.textContent = payload.sql;
          resultPanel.hidden = false;
          tableContainer.replaceChildren();
        }
        throw new Error(payload.error?.message || "The query could not be completed.");
      }
      renderResult(payload);
      if (payload.warning) {
        showStatus(payload.warning, "warning");
      } else {
        statusMessage.hidden = true;
      }
      await loadHistory();
    } catch (error) {
      showStatus(
        error instanceof TypeError
          ? "Could not reach InsightSQL. Check that the application is running."
          : error.message,
        "error",
      );
    } finally {
      setLoading(false);
    }
  });

  document.querySelectorAll(".example-chip").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question;
      questionInput.focus();
    });
  });

  document.querySelector("#refresh-history").addEventListener("click", loadHistory);

  async function loadHistory() {
    try {
      const response = await fetch("/api/history", {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error?.message || "Could not load query history.");
      }
      renderHistory(payload.items || []);
    } catch (error) {
      historyList.replaceChildren(makeText("Could not load query history.", "empty-state"));
    }
  }

  function renderResult(result) {
    sqlOutput.textContent = result.sql;
    rowCount.textContent = `${result.row_count} ${result.row_count === 1 ? "row" : "rows"}`;
    truncatedMessage.hidden = !result.truncated;
    truncatedMessage.textContent = result.truncated
      ? "Results were capped for safety. Refine your question to narrow the results."
      : "";
    tableContainer.replaceChildren();

    if (result.columns.length === 0) {
      tableContainer.append(makeText("The query returned no columns.", "empty-state"));
    } else if (result.rows.length === 0) {
      tableContainer.append(makeText("No matching records found.", "empty-state"));
    } else {
      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headerRow = document.createElement("tr");
      result.columns.forEach((column) => {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = column;
        headerRow.append(cell);
      });
      head.append(headerRow);
      const body = document.createElement("tbody");
      result.rows.forEach((row) => {
        const tableRow = document.createElement("tr");
        row.forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value === null ? "—" : String(value);
          tableRow.append(cell);
        });
        body.append(tableRow);
      });
      table.append(head, body);
      tableContainer.append(table);
    }

    resultPanel.hidden = false;
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderHistory(items) {
    historyList.replaceChildren();
    if (items.length === 0) {
      historyList.append(makeText("Your questions will appear here.", "empty-state"));
      return;
    }

    items.forEach((item) => {
      const article = document.createElement("article");
      article.className = "history-item";
      const content = document.createElement("div");
      content.className = "history-content";
      content.append(
        makeText(item.question, "history-question"),
        makeText(formatTimestamp(item.created_at), "history-time"),
      );
      const status = makeText(item.status, `history-status status-${item.status}`);
      const controls = document.createElement("div");
      controls.className = "history-controls";
      const showSql = document.createElement("button");
      showSql.className = "text-button";
      showSql.type = "button";
      showSql.textContent = "View SQL";
      showSql.addEventListener("click", () => {
        sqlOutput.textContent = item.sql || "No SQL was generated.";
        rowCount.textContent = item.row_count == null ? item.status : `${item.row_count} rows`;
        tableContainer.replaceChildren(
          makeText(
            item.error_message || "Select this question and run it again to refresh results.",
            "empty-state",
          ),
        );
        truncatedMessage.hidden = true;
        resultPanel.hidden = false;
        resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      const rerun = document.createElement("button");
      rerun.className = "text-button";
      rerun.type = "button";
      rerun.textContent = "Ask again";
      rerun.addEventListener("click", () => {
        questionInput.value = item.question;
        questionInput.focus();
        form.requestSubmit();
      });
      controls.append(showSql, rerun);
      article.append(content, status, controls);
      historyList.append(article);
    });
  }

  function makeText(text, className) {
    const element = document.createElement("p");
    element.className = className;
    element.textContent = text;
    return element;
  }

  function formatTimestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function showStatus(message, kind) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message status-${kind}`;
    statusMessage.hidden = false;
  }

  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    questionInput.disabled = isLoading;
    submitButton.querySelector(".button-label").textContent = isLoading
      ? "Working…"
      : "Generate & run";
  }

  loadHistory();
})();
