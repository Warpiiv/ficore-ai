workers = 3  # Adjust based on CPU cores (Render free tier typically has 1 CPU)
       worker_class = "sync"
       bind = "0.0.0.0:10000"
       accesslog = "-"
       errorlog = "-"
       loglevel = "info"