
document.addEventListener("DOMContentLoaded", () => {
  // HTML 요소 연결
  const chatMessages = document.getElementById("chat-container");
  const chatForm = document.querySelector(".chat-compose");
  const userInput = document.getElementById("user-input");
  const sendButton = document.getElementById("send-btn");
  const quickBtns = document.querySelectorAll(".quick-btn");
  const toneSelect = document.getElementById("ai-tone");
  const clearButton = document.getElementById("clear-btn");
  const charCount = document.getElementById("char-count");

  // 필수 요소 확인
  if (!chatMessages || !chatForm || !userInput || !sendButton) {
    console.error(
      "채팅 화면 요소를 찾을 수 없습니다. HTML의 ID를 확인해 주세요."
    );
    return;
  }

  const MAX_LENGTH = 1000;
  const REQUEST_TIMEOUT = 30000;

  let isSending = false;

  // 마지막 메시지까지 스크롤
  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // 전송 상태 변경
  function setSending(sending) {
    isSending = sending;

    userInput.disabled = sending;

    sendButton.disabled =
      sending || userInput.value.trim().length === 0;
  }

  // 글자 수 표시
  function updateCharCount() {
    if (charCount) {
      charCount.textContent =
        `${userInput.value.length} / ${MAX_LENGTH}`;
    }

    sendButton.disabled =
      isSending || userInput.value.trim().length === 0;
  }

  // 메시지 표시
  function appendMessage(sender, text, options = {}) {
    const {
      isAI = false,
      isError = false,
      isCrisis = false,
      retryText = null,
    } = options;

    const isUser = sender === "user";

    const message = document.createElement("div");
    message.className =
      `chat-message ${isUser ? "user-message" : "ai-message"}`;

    if (isError) {
      message.classList.add("error-message");
    }

    if (isCrisis) {
      message.classList.add("crisis-message");
    }

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.textContent = isUser ? "나" : "AI";

    const column = document.createElement("div");
    column.className = "chat-message-column";

    // 실제 AI 생성 답변에만 라벨 표시
    if (!isUser && isAI) {
      const senderLabel = document.createElement("div");
      senderLabel.className = "chat-sender-label";
      senderLabel.textContent = "✦ PickMe AI 답변";
      column.appendChild(senderLabel);
    }

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";

    // 사용자 입력을 HTML로 실행하지 않도록 처리
    bubble.textContent = String(text ?? "");

    column.appendChild(bubble);

    // 오류가 발생하면 다시 시도 버튼 표시
    if (isError && retryText) {
      const retryButton = document.createElement("button");
      retryButton.type = "button";
      retryButton.className = "chat-retry-button";
      retryButton.textContent = "다시 시도";

      retryButton.addEventListener("click", () => {
        sendMessage(retryText);
      });

      column.appendChild(retryButton);
    }

    message.appendChild(avatar);
    message.appendChild(column);
    chatMessages.appendChild(message);

    scrollToBottom();

    return message;
  }

  // AI 응답 대기 표시
  function showTyping() {
    const typing = document.createElement("div");
    typing.className =
      "chat-message ai-message typing-message";
    typing.id = "typingIndicator";

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.textContent = "AI";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble typing-bubble";
    bubble.textContent = "답변을 준비하고 있어요...";

    typing.appendChild(avatar);
    typing.appendChild(bubble);
    chatMessages.appendChild(typing);

    scrollToBottom();
  }

  // AI 응답 대기 표시 제거
  function hideTyping() {
    const typing = document.getElementById("typingIndicator");

    if (typing) {
      typing.remove();
    }
  }

  // 분석된 선택지 표시
  function showParsedData(parsedData) {
    if (!parsedData) {
      return;
    }

    const optionA = parsedData.option_a;
    const optionB = parsedData.option_b;

    if (!optionA || !optionB) {
      return;
    }

    const banner = document.createElement("div");
    banner.className = "parsed-options-banner";

    const title = document.createElement("div");
    title.className = "parsed-options-title";
    title.textContent = "비교할 선택지";

    const options = document.createElement("div");
    options.className = "parsed-options";

    const optionAElement = document.createElement("span");
    optionAElement.className = "parsed-option";
    optionAElement.textContent = optionA;

    const versus = document.createElement("span");
    versus.className = "parsed-versus";
    versus.textContent = "VS";

    const optionBElement = document.createElement("span");
    optionBElement.className = "parsed-option";
    optionBElement.textContent = optionB;

    options.append(
      optionAElement,
      versus,
      optionBElement
    );

    banner.append(title, options);
    chatMessages.appendChild(banner);

    scrollToBottom();
  }

  // 메시지 전송
  async function sendMessage(rawMessage) {
    const message = String(
      rawMessage ?? userInput.value
    ).trim();

    if (!message || isSending) {
      return;
    }

    if (message.length > MAX_LENGTH) {
      appendMessage(
        "ai",
        `메시지는 ${MAX_LENGTH}자 이내로 입력해 주세요.`,
        { isError: true }
      );
      return;
    }

    // 사용자 메시지를 채팅 화면에 표시
    appendMessage("user", message);

    userInput.value = "";
    updateCharCount();

    setSending(true);
    showTyping();

    const controller = new AbortController();

    const timeoutId = window.setTimeout(() => {
      controller.abort();
    }, REQUEST_TIMEOUT);

    try {
      const selectedTone =
        toneSelect?.value ||
        localStorage.getItem("pickme-tone") ||
        "empathy";

      localStorage.setItem("pickme-tone", selectedTone);

      const response = await fetch("/chat/api/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          message,
          tone: selectedTone,
        }),
        signal: controller.signal,
      });

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error("서버 응답을 읽을 수 없습니다.");
      }

      hideTyping();

      const requestSucceeded =
        response.ok && data.status === "success";

      if (!requestSucceeded) {
        appendMessage(
          "ai",
          data.reply ||
            "요청을 처리하지 못했습니다. 다시 시도해 주세요.",
          {
            isError: true,
            isAI: false,
            retryText: message,
          }
        );
        return;
      }

      appendMessage("ai", data.reply, {
        isError: false,
        isCrisis: Boolean(data.is_crisis),
        isAI: data.is_ai === true,
      });

      if (
        !data.is_crisis &&
        !data.is_harmful &&
        !data.is_general_chat
      ) {
        showParsedData(data.parsed_data);
      }
    } catch (error) {
      hideTyping();

      const errorMessage =
        error.name === "AbortError"
          ? "응답 시간이 초과됐어요. 잠시 후 다시 시도해 주세요."
          : "서버에 연결할 수 없습니다. 네트워크 상태를 확인하고 다시 시도해 주세요.";

      appendMessage("ai", errorMessage, {
        isError: true,
        isAI: false,
        retryText: message,
      });

      console.error("채팅 요청 오류:", error);
    } finally {
      window.clearTimeout(timeoutId);
      setSending(false);
      updateCharCount();
      userInput.focus();
    }
  }

  // 폼 제출 처리
  chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });

  // 전송 버튼 클릭
  sendButton.addEventListener("click", () => {
    sendMessage();
  });

  // 입력 시 글자 수 갱신 및 버튼 활성화
  userInput.addEventListener("input", updateCharCount);

  // Enter 전송, Shift + Enter 줄바꿈
  userInput.addEventListener("keydown", (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.isComposing
    ) {
      event.preventDefault();

      if (!sendButton.disabled) {
        sendMessage();
      }
    }
  });

  // 빠른 선택 질문
  quickBtns.forEach((button) => {
    button.addEventListener("click", () => {
      const message = button.dataset.message;

      if (message) {
        sendMessage(message);
      }
    });
  });

  // 상담 스타일 설정 복원 및 저장
  if (toneSelect) {
    toneSelect.value =
      localStorage.getItem("pickme-tone") || "empathy";

    toneSelect.addEventListener("change", () => {
      localStorage.setItem(
        "pickme-tone",
        toneSelect.value
      );
    });
  }

  // 채팅 초기화
  if (clearButton) {
    clearButton.addEventListener("click", () => {
      if (isSending) {
        return;
      }

      chatMessages.replaceChildren();
      userInput.value = "";

      updateCharCount();
      userInput.focus();
    });
  }

  // 초기 상태 설정
  updateCharCount();
});
