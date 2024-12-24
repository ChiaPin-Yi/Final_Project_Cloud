$(function(){
    $("#submit").click(chatWithLLM);
    $("#message").keypress(function(e){
        if(e.which == 13){
            chatWithLLM();
        }
    });
    const attachButton = document.getElementById('attachButton');
    const fileInput = document.getElementById('fileInput');

    // 限制只能選取圖片檔案
    fileInput.setAttribute("accept", "image/*");
    fileInput.setAttribute("multiple", true);

    // 監聽按鈕點擊事件
    attachButton.addEventListener('click', () => {
        fileInput.click(); // 觸發文件選擇框
    });

    // 監聽文件選擇變化
    fileInput.addEventListener('change', (event) => {
        const files = event.target.files;
        if (files.length > 0) {
            let invalidFiles = [];
            Array.from(files).forEach(file => {
                if (!file.type.startsWith("image/")) {
                    invalidFiles.push(file.name);
                }
            });

            if (invalidFiles.length > 0) {
                alert(`以下檔案不是圖片：\n${invalidFiles.join("\n")}`);
                fileInput.value = ""; // 清空選擇
                return;
            }

            // 顯示選取的圖片檔案名稱
            const fileNames = Array.from(files).map(file => file.name).join(", ");
            $("#message").val(`以選取圖片${files.length}張圖片，分別是: ${fileNames}`);
        }
    });
});

function chatWithLLM(){
    var message = $("#message").val();
    if (message.trim() === "") return;

    // 插入使用者訊息
    var userMessage = $("<div></div>").addClass("message user-message").text(message);
    $("#dialog").append(userMessage);

    var data = { message: message };
    $.post("/call_llm", data, function(response){
        // 插入 AI 回應
        var aiMessage = $("<div></div>").addClass("message ai-message").text(response);
        $("#dialog").append(aiMessage);

        // 滾動到最新
        $("#dialog").scrollTop($("#dialog")[0].scrollHeight);
    });

    // 清空輸入框並滾動到最新
    $("#message").val("");
    $("#dialog").scrollTop($("#dialog")[0].scrollHeight);
}