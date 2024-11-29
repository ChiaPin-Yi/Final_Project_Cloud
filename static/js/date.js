let millisecsPerDay=24*60*60*1000;
let startdate=new Date;
let stringtime=new Date(startdate.getTime()+7*2*millisecsPerDay);
let day=startdate.getDate(),month=startdate.getMonth()+1,year=startdate.getFullYear(),week=startdate.getDay();
let day2=stringtime.getDate(),month2=stringtime.getMonth()+1,year2=stringtime.getFullYear();
var nowday=[],maxday=[];
nowday+=year+"-";
if(month<10)
{
    nowday+='0'+month;
}
else{
    nowday+=month;
}
nowday+="-";
if(day<10)
{
    nowday+='0'+day;
}
else{
    nowday+=day;
}
maxday+=year2+"-";
if(month2<10)
{
    maxday+='0'+month2;
}
else{
    maxday+=month2;
}
maxday+="-";
if(day2<10)
{
    maxday+='0'+day2;
}
else{
    maxday+=day2;
}

function findweek(e){
    var date=new Date(e);
    week=date.getDay();
    console.log("week:"+week);
}