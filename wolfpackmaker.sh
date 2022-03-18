python_bin=$(which python)

echo $python_bin

$python_bin -m pip install -r src/requirements-client.txt

$python_bin src/src/launch.py $@

sleep 10


