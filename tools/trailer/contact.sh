#!/usr/bin/env bash
# Contact sheet of a clip: N evenly spaced frames in a grid. Usage: contact.sh clip.mp4 out.jpg [N=12] [cols=4]
set -euo pipefail
in=$1; out=$2; n=${3:-12}; cols=${4:-4}
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$in")
rows=$(( (n + cols - 1) / cols ))
fps=$(python3 -c "print($n/$dur)")
nice -n 10 ffmpeg -loglevel error -y -i "$in" -vf "fps=$fps,scale=480:270,drawtext=text='%{pts\:hms}':x=8:y=8:fontcolor=yellow:fontsize=18:box=1:boxcolor=black@0.6,tile=${cols}x${rows}" -frames:v 1 -threads 4 "$out"
