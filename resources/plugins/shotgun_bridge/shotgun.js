
function ShotgunConnection(webSocket) 
{
  this.logUserInfo = function logUserInfo(str)
  {
      alg.log.info("<font color=#00FF00>"+str+"</font>")
  }
}


function createShotgunConnection() {
  new ShotgunConnection();
}
