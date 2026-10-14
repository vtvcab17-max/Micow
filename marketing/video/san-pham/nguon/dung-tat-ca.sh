set -e
mkdir -p ra
for app in bravin antifact micron micow; do
  vo=giong/$app.mp3; mu=nhac/$app/mix.wav
  voend=$(python3 -c "import json;print(json.load(open('giong/$app.json'))['segs'][-1]['end'])")
  for o in h v; do
    rm -rf khung-$app-$o; node dung.js $app $o khung-$app-$o
    total=$(cat khung-$app-$o/total.txt); fo=$(python3 -c "print(round($total-1.2,2))")
    ten=$app-$([ $o = h ] && echo 16x9 || echo 9x16)
    ffmpeg -v error -y -framerate 30 -i khung-$app-$o/f%04d.jpg -i $vo -i $mu -filter_complex \
      "[2:a]volume='if(lt(t,$voend+0.2),0.2,0.75)':eval=frame,afade=t=out:st=$fo:d=1.2[m];[1:a]aresample=48000,apad[v];[v][m]amix=inputs=2:normalize=0:duration=longest,atrim=0:$total,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
      -map 0:v -map "[a]" -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart -t $total ra/$ten.mp4
    rm -rf khung-$app-$o
    echo "XONG $ten"
  done
done
echo "TẤT CẢ XONG"
