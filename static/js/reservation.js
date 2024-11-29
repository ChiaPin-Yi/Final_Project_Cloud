let moviesource = []; // 初始化为空，数据从后端加载

$(function () {
    loadMovieSource(); // 页面加载时动态获取电影数据
    $("#go").on("click", load);
});

// 动态加载电影数据
function loadMovieSource() {
    let url = "/api/moviesource"; // 对应后端的 API 路径
    $.getJSON(url)
        .done(function (data) {
            moviesource = data; // 更新全局变量 moviesource
            console.log("Moviesource loaded:", moviesource);
        })
        .fail(function () {
            console.error("Failed to load moviesource!");
        });
}

let position=["","A","B","","C","D","E","F","G","H","","I","J"]
function load(){
    // console.log("s");
    $("#result").empty();
    let user_name = $("#name").val(); // 获取输入框中的用户名
    let url = `/reservation/api?user_name=${user_name}`; // 将 user_name 添加到请求参数中

    $.getJSON(url)
        .done(function (msg) {
            $("#result").empty(); // 清空结果区域
            if (msg.error) {
                console.log(msg.error);
                return;
            }
            msg.forEach((reservation) => {
                let seat = "Seat : ";
                let seats = reservation.seats.split(","); // 将逗号分隔的座位解析为数组
                seats.forEach((seatCode) => {
                    let row = Math.floor(seatCode / 100) - 1; // 行号
                    let col = seatCode % 100; // 列号
                    seat += position[col] + row + " ";
                });

                let date = `Date : ${new Date(reservation.reservation_date).toISOString().split("T")[0]}`; // 提取 YYYY-MM-DD 部分
                let time = `Time : ${reservation.reservation_time.slice(0, 5)}`; // 提取 HH:MM 部分
                let title = `Title : ${moviesource[reservation.movie_id - 1].name}`;
                let url_image = `static/${moviesource[reservation.movie_id - 1].src}`;
                console.log(date);
                console.log(time);
                console.log(title);
                $("#result").append(
                    `<hr>
                    <div class="button">
                        <img class="ii" src="${url_image}">
                        <h4 class="inf">${title}</h4>
                        <h4 class="inf">${date}</h4>
                        <h4 class="inf">${time}</h4>
                        <h4 class="inf">${seat}</h4>
                        <input class="bgb" type="button" value="delete" onclick="makedelete(${reservation.id})">
                    </div>`
                );
            });
        })
        .fail(function (msg) {
            console.log("Fail to load reservations!");
        });
}

function makedelete(reservationId) {
    // 定义后端 DELETE API 的 URL
    let url = `/reservation/api?id=${reservationId}`;

    // 构造需要发送的 JSON 数据（如果需要附加参数，例如删除原因）
    let data = JSON.stringify({
        reason: "User canceled the reservation" // 可选的附加信息
    });

    // 发起 AJAX DELETE 请求
    $.ajax({
        url: url,
        type: 'DELETE', // 指定 HTTP 方法为 DELETE
        contentType: "application/json", // 告诉后端数据类型是 JSON
        data: data, // JSON 数据
        success: function(response) {
            // 如果删除成功
            console.log("Delete successful:", response);
            alert("Reservation deleted successfully!");

            // 根据删除的 reservationId 移除对应的 HTML 元素（假设元素 ID 是动态生成的）
            $("#result").empty();
        },
        error: function(xhr, status, error) {
            // 如果请求失败，处理错误响应
            console.error("Failed to delete reservation:", xhr.responseJSON);
            alert("Failed to delete reservation: " + (xhr.responseJSON?.error || error));
        }
    });
}

function moreorless(y,m,d,yt,mt,dt)
{
    if(y<yt)
    {
        return false;
    }
    else if(y>yt)
    {
        return true;
    }
    else
    {
        if(m<mt)
        {
            return false;
        }
        else if(m>mt)
        {
            return true;
        }
        else{
            if(d<dt)
            {
                return false;
            }
            else
            {
                return true;
            }
        }
    }
}