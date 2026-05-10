document.addEventListener("DOMContentLoaded", () => {
  const widget = document.getElementById("chatbot-widget");
  const toggle = document.getElementById("chatbot-toggle");
  const closeBtn = document.getElementById("chatbot-close");
  const panel = document.getElementById("chatbot-panel");
  const form = document.getElementById("chatbot-form");
  const input = document.getElementById("chatbot-input");
  const messages = document.getElementById("chatbot-messages");
  const vehicleSelect = document.getElementById("chatbot-vehicle");

  if (!widget || !toggle || !panel || !form || !input || !messages) return;

  const replyUrl = widget.dataset.replyUrl || "/chatbot/reply/";
  const vehiclesUrl = widget.dataset.vehiclesUrl || "/chatbot/vehicles/";
  let vehiclesLoaded = false;
  let vehicleLoadErrorShown = false;

  const addMessage = (text, type) => {
    const div = document.createElement("div");
    div.className = `chatbot-message ${type}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  };

  const getCsrfToken = () => {
    const csrfInput = form.querySelector("[name=csrfmiddlewaretoken]");
    return csrfInput ? csrfInput.value : "";
  };

  const hasVehicleOptions = () => {
    if (!vehicleSelect) return false;
    return Array.from(vehicleSelect.options).some((option) => option.value);
  };

  const loadVehicles = async () => {
    if (!vehicleSelect) return;

    try {
      const response = await fetch(vehiclesUrl, {
        method: "GET",
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (!response.ok) {
        throw new Error(`Vehicle endpoint returned ${response.status}`);
      }

      const data = await response.json();

      vehicleSelect.innerHTML = "";

      if (!data.vehicles || data.vehicles.length === 0) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "No vehicle available";
        vehicleSelect.appendChild(option);
        return;
      }

      if (data.vehicles.length > 1) {
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Choose a vehicle";
        vehicleSelect.appendChild(defaultOption);
      }

      data.vehicles.forEach((vehicle) => {
        const option = document.createElement("option");
        option.value = vehicle.id;
        option.textContent = vehicle.label;
        vehicleSelect.appendChild(option);
      });
      vehiclesLoaded = true;
    } catch (error) {
      if (!hasVehicleOptions()) {
        vehicleSelect.innerHTML = '<option value="">Vehicle list unavailable</option>';
      }
      if (!vehicleLoadErrorShown) {
        addMessage("Vehicle list could not refresh. Using the vehicles already loaded on this page.", "bot");
        vehicleLoadErrorShown = true;
      }
      vehiclesLoaded = hasVehicleOptions();
    }
  };

  toggle.addEventListener("click", () => {
    panel.classList.toggle("d-none");
    if (!panel.classList.contains("d-none")) {
      if (!vehiclesLoaded) {
        loadVehicles();
      }
      input.focus();
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      panel.classList.add("d-none");
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";

    const loadingMessage = document.createElement("div");
    loadingMessage.className = "chatbot-message bot";
    loadingMessage.textContent = "Thinking...";
    messages.appendChild(loadingMessage);
    messages.scrollTop = messages.scrollHeight;

    try {
      const response = await fetch(replyUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          message: text,
          vehicle_id: vehicleSelect ? vehicleSelect.value : null,
        }),
      });

      const data = await response.json();
      loadingMessage.remove();

      if (!response.ok) {
        addMessage(data.error || "Chatbot error.", "bot");
        return;
      }

      addMessage(data.reply || "No response.", "bot");
    } catch (error) {
      loadingMessage.remove();
      addMessage("Chatbot service unavailable.", "bot");
    }
  });
});
