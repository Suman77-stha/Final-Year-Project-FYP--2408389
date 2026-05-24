/* ==============================
   GLOBAL VARIABLES
============================== */
const micBtn = document.getElementById('mic-btn');
const messageInput = document.getElementById('message-input');
const chatForm = document.getElementById('chat-form');
const chatWindow = document.getElementById('chat-window');

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition;
let isListening = false;

/* ==============================
   INITIALIZE SPEECH RECOGNITION
============================== */
if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = false; // single phrase at a time
    recognition.interimResults = false;

    /* ===== START LISTENING ===== */
    function startListening() {
        try {
            if (!isListening) {
                recognition.start();
                isListening = true;
                micBtn.style.color = "#ff4b2b"; // red while listening
                micBtn.innerHTML = '<i class="fas fa-microphone-slash"></i>';
                messageInput.placeholder = "Listening...";
            }
        } catch (e) {
            console.log("Speech recognition already started");
        }
    }

    /* ===== STOP LISTENING ===== */
    function stopListening() {
        try {
            recognition.stop();
        } catch (e) {}
        isListening = false;
        micBtn.style.color = "#aaa";
        micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        messageInput.placeholder = "Ask me about stocks...";
    }

    /* ===== CLICK MIC BUTTON ===== */
    micBtn.addEventListener('click', () => {
        if (!isListening) {
            startListening();
        } else {
            stopListening();
        }
    });

    /* ===== ON RESULT ===== */
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        messageInput.value = transcript;
        stopListening();
        // Auto-submit form
        chatForm.submit();
    };

    /* ===== ON END ===== */
    recognition.onend = () => {
        stopListening();
    };

    /* ===== ERROR HANDLER ===== */
    recognition.onerror = (event) => {
        console.log("Speech recognition error:", event.error);
        stopListening();
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
            alert("Microphone access denied. Please allow microphone to use voice.");
        }
    };

} else {
    micBtn.style.display = "none";
    console.warn("Speech recognition not supported in this browser.");
}

/* ==============================
   TEXT-TO-SPEECH FUNCTION
============================== */
function speakAI(text) {
    if (!text) return;
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-US";
    speech.rate = 1;
    speech.pitch = 1;
    window.speechSynthesis.speak(speech);
}

/* ==============================
   AUTO SPEAK LAST AI RESPONSE
============================== */
function autoSpeakLastMessage() {
    const messages = document.querySelectorAll(".ai-message");
    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1].innerText;
        speakAI(lastMessage);
    }
}

/* ==============================
   SCROLL TO BOTTOM & AUTO SPEAK
============================== */
function scrollAndSpeak() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
    autoSpeakLastMessage();
}

/* ==============================
   ON PAGE LOAD
============================== */
window.onload = function() {
    // Scroll & speak last AI message
    scrollAndSpeak();
};

/* ==============================
   LISTEN TO NEW AI MESSAGES AFTER FORM SUBMIT
============================== */
const chatObserver = new MutationObserver(() => {
    scrollAndSpeak();
});

chatObserver.observe(chatWindow, { childList: true });