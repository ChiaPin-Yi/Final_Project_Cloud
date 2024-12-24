var reservation={title:"",name:"",date:"",time:"",seat:[],ticket};
var ticket=0;
var ticket2=0;
var tt;
var court=["A","B","C","D","E","F","G"];
$(function(){
    $("#firstdate").val(nowday);
    $("#firstdate").attr("max",maxday);
    $("#firstdate").attr("min",nowday);
    console.log(nowday);
    console.log(maxday);
    $.getJSON('/api/moviesource', function (data) {
        // 將 moviesource 賦值為從後端獲取的數據
        window.moviesource = data;
        // 初始化下拉選單
        $("#moviename").append(
            `<option></option>`
        );
        for (let x = 0; x < moviesource.length; x++) {
            $("#moviename").append(
                `<option value='${x}'>${moviesource[x].name}</option>`
            );
        }
    }).fail(function () {
        console.error("Failed to load moviesource data.");
    });

    $("#moviename").on("change",loadOnlyFilm);
    // $("button").on("change",loadserverdata);
});
select_movie_id=0;
function loadOnlyFilm(){
    select_movie_id=Number(this.value)+1;
    $("#courseTable").empty();
        console.log(this.value);
        
        $("#onlyimg").attr("src","static/"+moviesource[this.value].src);
        $("#onlyh").text(moviesource[this.value].name);
        console.log(moviesource[this.value].name);
        var tt=[0,moviesource[this.value].time];
        checktime(tt);
        $("#onlyp").text("Movie Duration : "+tt[0]+" h "+tt[1]+" m ");
        let date = $("#firstdate").val();  // 当前选择的日期
        reservation.date=$("#firstdate").val();
        let url = `/api/movie/${select_movie_id}/showtimes?date=${date}`;

        $.getJSON(url)
            .done(function (msg) {
                // 清空现有的内容
                $("#courseTable").empty();

                // 遍历放映厅和场次
                for (let room in msg.showtimes) {
                    $("#courseTable").append(`<h3>${room}</h3><br>`);

                    // 遍历时间
                    msg.showtimes[room].forEach(time => {
                        $("#courseTable").append(
                            `<input class="ch" type="button" value="${time}" onclick="booking(value)">`
                        );
                    });

                    $("#courseTable").append(`<br><br><br><br>`);
                }
            })
            .fail(function () {
                console.log("Fail to load showtimes!");
            });
}
function loadserverdata(){
    if(this.value==0)return;

}

function checktime(x){
    while(x[1]>59)
    {
        x[0]++;
        x[1]-=60;
    }
    while(x[0]>23)
    {
        x[0]-=24;
    }
}
function booking(time){
    console.log(time);
    $("#onlyp").empty();
    $("#bookingpage").empty();
    $("#seattable").css("display","block");
    reservation.date=$("#firstdate").val();
    reservation.time=time;
    findthebooking();
    $("#bookingpage").append(
        `<div id="bd">
        <img id="onlyimg" src="${$("#onlyimg")[0].src}">
        <h3>${$("#onlyh").text()}</h3>
        </div>
        `+
        `<div id="bd2">
        <h2>Informaton:</h2>
        <h3>Date : ${$("#firstdate").val()}
        <h3>Time : ${time}
        <h3>Choose your seat:
        </div>
        <div id="bd3">
        <h3>Your name:</h3>
        <input type="text" class="namebox">
        </div>
        `
    )
    tt=time;
    console.log(reservation);
    $("#bookingpage").append(
        `<div id="bb"><button class="bb2 bb2b">Back</button><button class="bb2 bb2n">Next</button><div>`
    )
    $("#bookingpage").css("display","block");
    
    $(".seat").on("click",findseat);
    $(".bb2b").on("click",back);
    $(".bb2n").on("click",next);
}

function findseat(){
    if($(this).is(".color"))
    {
        ticket--;
        $(this).removeClass("color");
    }
    else
    {
        ticket++;
        $(this).addClass("color");
    }
    
}
function back(){
    $(".seat").each(function(){
        if($(this).is(".color"))
       {
        ticket=0;
        $(this).removeClass("color");
       }
    });
    $("#seattable").css("display","none");
    $("#bookingpage").css("display","none");
    $(".seat").on("click",findseat);
    location.reload();
}
function next(){
    if(ticket==0||$(".namebox").val()=="")
    {
        alert("Please choose a seat or enter your name");
        return false;
    }
    reservation.name=$(".namebox").val();
    reservation.ticket=ticket;
    console.log(reservation);
    $("#bookingpage").empty();
    $("#bookingpage").append(
        `<h3>Early Bird Ticket:</h3>
        <select class="ticketselect s">Early Bird Ticket</select><br>
        <h3>Adult Ticket:</h3>
        <select class="ticketselect1 s">Adult Ticket</select><br>
        <h3>Concession Ticket:</h3>
        <select class="ticketselect2 s">Concession Ticket</select><br>
        <h3 class="total">Total:</h3>
        
        <button class="bbb">Confirm</button>
        `
    )
    addtickettype($(".ticketselect"));
    addtickettype($(".ticketselect1"));
    addtickettype($(".ticketselect2"));
    $("table").css("left","40%");
    $(".s").on("change",finaltotal);
    $(".bbb").on("click",bookcomplete);
}

function addtickettype(e){
    for(var x=0;x<=ticket;x++)
    {
        $(e).append(
            `<option value='${x}'>${x}</option>`
        );
    }
}

function finaltotal(){
    var money=0;
    var to="Total : ";
    var cm=$(".ticketselect").val()*1+$(".ticketselect1").val()*1+$(".ticketselect2").val()*1;
    ticket2=cm;
    if(cm>ticket)
    {
        $(".s").val(0);
        console.log("out of range");
    }
    else
    {
        money=$(".ticketselect").val()*220+$(".ticketselect1").val()*290+$(".ticketselect2").val()*270;
    }
    $(".total").text(to+money);
}

function bookcomplete()
{
    ticket2=$(".ticketselect").val()*1+$(".ticketselect1").val()*1+$(".ticketselect2").val()*1;
    console.log(ticket);
    if(ticket!=ticket2)
    {
        return false;
    }
    else{
        $(".color").each(function(){
            var i=$(this).parent().parent().find("tr").index($(this).parent()[0]);
            var i2=$(this).index(),ii;
            // 補齊列索引，確保格式統一
            var ii = i2 < 10 ? "0" + i2 : i2;

            // 將座位以字符串格式存入 reservation.seat 陣列
            reservation.seat.push(i + "" + ii);
            $(this).removeClass("color");
            $(this).addClass("booking");
        });
        console.log(reservation.seat);
        let url = "/reservation/api";  // 改为后端的 POST 接口路径
        console.log(reservation);
        $.post({
            url: url,
            contentType: "application/json",  // 设置 Content-Type 为 JSON
            data: JSON.stringify({           // 使用 JSON.stringify 序列化数据
                movie_id: select_movie_id,
                user_name: reservation.name,
                date: reservation.date,
                time: reservation.time,
                ticket: reservation.ticket,
                seat: reservation.seat
            })
        })
        .done(function(msg) {
            console.log("Reservation successful:", msg);
        })
        .fail(function(msg) {
            console.log("Reservation failed:", msg);
        });
        ticket2=0;
        ticket=0;
        alert("booking complete!");
        location.reload();
    }
}

function findthebooking() {
    if (!reservation.time || !reservation.date || !select_movie_id) {
        console.error("Missing required parameters!");
        return;
    }

    // 如果時間格式為 HH:MM，補全為 HH:MM:SS
    if (reservation.time.length === 5) {
        reservation.time += ":00";
    }

    console.log(`Movie ID: ${select_movie_id}, Date: ${reservation.date}, Time: ${reservation.time}`);

    let url = `/reservation/api?movie_id=${select_movie_id}&reservation_date=${reservation.date}&reservation_time=${reservation.time}`;
    
    $.getJSON(url)
        .done(function (data) {
            console.log("Fetched reservation data:", data);

            // 遍歷座位信息，標記為已預訂
            $(".seat").each(function () {
                var i = $(this).parent().parent().find("tr").index($(this).parent()[0]);
                var ii = $(this).index();

                data.forEach(reservation => {
                    let reservedSeats = reservation.seats ? reservation.seats.split(",") : [];
                    reservedSeats.forEach(seat => {
                        let reservedSeatIndex = parseInt(seat);
                        if ((i * 100 + ii) === reservedSeatIndex) {
                            $(this).addClass("booking");
                        }
                    });
                });
            });
        })
        .fail(function () {
            console.error("Failed to fetch reservation data!");
        });
}

