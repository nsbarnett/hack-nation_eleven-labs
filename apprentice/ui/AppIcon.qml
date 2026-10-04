import QtQuick

// Small original vector icons; no platform-dependent font glyphs or downloads.
Canvas {
    id: icon
    property string name: "wave"
    property color color: Theme.text
    implicitWidth: 20; implicitHeight: 20
    onNameChanged: requestPaint()
    onColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset(); c.scale(width / 24, height / 24);
        c.strokeStyle = color; c.fillStyle = color; c.lineWidth = 1.65;
        c.lineCap = "round"; c.lineJoin = "round";
        function line(points) { c.beginPath(); c.moveTo(points[0][0], points[0][1]); for (var i=1;i<points.length;i++) c.lineTo(points[i][0], points[i][1]); c.stroke(); }
        function circle(x,y,r,fill) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); fill ? c.fill() : c.stroke(); }
        function box(x,y,w,h) { c.strokeRect(x,y,w,h); }
        switch (name) {
        case "home": line([[3,11],[12,3],[21,11]]); line([[5,10],[5,21],[10,21],[10,15],[14,15],[14,21],[19,21],[19,10]]); break;
        case "capture": circle(12,12,9,false); circle(12,12,4,true); break;
        case "record": circle(12,12,6,true); break;
        case "stop": c.fillRect(6,6,12,12); break;
        case "pause": c.fillRect(6,5,4,14); c.fillRect(14,5,4,14); break;
        case "play": c.beginPath(); c.moveTo(7,4); c.lineTo(20,12); c.lineTo(7,20); c.closePath(); c.fill(); break;
        case "map": circle(5,5,2,false); circle(19,5,2,false); circle(12,19,2,false); line([[7,5],[17,5]]); line([[5,8],[5,12],[12,12],[12,17]]); break;
        case "teach": line([[2,8],[12,3],[22,8],[12,13],[2,8]]); line([[6,10],[6,17],[12,20],[18,17],[18,10]]); line([[22,8],[22,16]]); break;
        case "context": case "evidence": line([[5,3],[14,3],[19,8],[19,21],[5,21],[5,3]]); line([[14,3],[14,8],[19,8]]); line([[8,12],[16,12]]); line([[8,16],[14,16]]); break;
        case "library": box(4,3,6,18); box(13,3,6,18); line([[6,7],[8,7]]); line([[15,7],[17,7]]); break;
        case "settings": circle(12,12,4,false); circle(12,12,8,false); for(var j=0;j<8;j++){var a=j*Math.PI/4;line([[12+8*Math.cos(a),12+8*Math.sin(a)],[12+10*Math.cos(a),12+10*Math.sin(a)]]);} break;
        case "mic": c.beginPath(); c.roundedRect(9,3,6,12,3,3); c.stroke(); c.beginPath(); c.arc(12,12,7,0,Math.PI); c.stroke(); line([[12,19],[12,22]]); line([[9,22],[15,22]]); break;
        case "mute": case "sound": line([[4,9],[8,9],[13,5],[13,19],[8,15],[4,15],[4,9]]); if(name==="mute") {line([[17,9],[22,15]]);line([[22,9],[17,15]]);} else {c.beginPath();c.arc(13,12,7,-0.8,0.8);c.stroke();} break;
        case "open": line([[13,4],[20,4],[20,11]]); line([[20,4],[10,14]]); line([[9,5],[4,5],[4,20],[19,20],[19,15]]); break;
        case "arrow": line([[4,12],[20,12]]); line([[14,6],[20,12],[14,18]]); break;
        case "up": line([[6,14],[12,8],[18,14]]); break;
        case "down": line([[6,10],[12,16],[18,10]]); break;
        case "plus": line([[5,12],[19,12]]); line([[12,5],[12,19]]); break;
        case "check": line([[4,12],[9,17],[20,6]]); break;
        case "close": line([[6,6],[18,18]]); line([[18,6],[6,18]]); break;
        case "screen": c.beginPath(); c.roundedRect(3,4,18,13,2,2); c.stroke(); line([[12,17],[12,21]]); line([[8,21],[16,21]]); break;
        default: line([[3,10],[3,14]]); line([[7.5,6],[7.5,18]]); line([[12,3],[12,21]]); line([[16.5,8],[16.5,16]]); line([[21,10],[21,14]]);
        }
    }
}
