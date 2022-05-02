from wolfpackmaker.wolfpackmaker import WolfpackMaker


w = WolfpackMaker()
w.main()
w.log.save_log(w.name, w.cached_dir)

