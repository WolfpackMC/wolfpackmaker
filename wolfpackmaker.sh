python_bin=$(which python)

echo $python_bin

$python_bin -m pip install -r requirements-client.txt

$python_bin wolfpackmaker.py $1

sleep 3


