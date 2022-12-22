
# movielens
# CUDA_VISIBLE_DEVICES=1 python main.py --model=bert4rec --mode=ml-1m --data_path=./Data/ml-1m/ratings.dat --min_sub_window_size=2 --max_seq_len=30 --num_samples=25 --num_query_set=3 --min_sequence=5 --min_item=50 --val_size=600 --num_test_data=1000 --num_train_iterations=2000 --load_pretrained_embedding=True --use_adaptive_loss=True --use_mlp_mean=False --use_softmax=False --lstm_lr=1e-1 --lstm_input=8 --lstm_hidden=128 --test --checkpoint_step=650

#amazon :
#  CUDA_VISIBLE_DEVICES=0 python main.py --model=bert4rec --mode=amazon --data_path=./Data/amazon/grocery_ratings.csv --min_sub_window_size=2 --max_seq_len=30 --num_samples=25 --num_query_set=3 --min_item=50 --min_sequence=5 --val_size=1000 --num_test_data=5000 --num_train_iterations=3000 --load_pretrained_embedding=True --use_adaptive_loss=True --use_mlp_mean=False --lstm_lr=1e-1 --lstm_input=16 --lstm_hidden=32 --inner_lr=1e-3 --test --checkpoint_step=3000

#amazon maml:
CUDA_VISIBLE_DEVICES=2 python main.py --model=bert4rec --mode=amazon --data_path=./Data/amazon/grocery_ratings.csv --min_sub_window_size=2 --max_seq_len=30 --num_samples=25 --num_query_set=3 --min_item=50 --min_sequence=5 --val_size=1000 --num_test_data=5000 --num_train_iterations=3000 --load_pretrained_embedding=True --use_adaptive_loss=False --test --checkpoint_step=2550