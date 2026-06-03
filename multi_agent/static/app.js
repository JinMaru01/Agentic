async function sendMessage() {

    const input = document.getElementById("message");

    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message: input.value
        })
    });

    const data = await response.json();

    document.getElementById("chat-box").innerHTML += `
        <div>
            <b>You:</b> ${input.value}
        </div>
        <div>
            <b>${data.agent}:</b> ${data.answer}
        </div>
        <hr>
    `;

    input.value = "";
}