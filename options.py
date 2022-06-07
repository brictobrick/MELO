import argparse


parser = argparse.ArgumentParser('Train a MAML!')
# about log and data
parser.add_argument('--log_dir', type=str, default='./log',
                    help='directory to save to or load from')
parser.add_argument('--data_path', type=str, default='./Data/ml-1m/ratings.dat',
                    help='data path')
parser.add_argument('--mode', type=str, default='ml-1m',
                    help='ml-1m or amazon')
parser.add_argument('--test', default=False, action='store_true',
                    help='train or test')
parser.add_argument('--checkpoint_step', type=int, default=-1,
                    help=('checkpoint iteration to load for resuming '
                          'training, or for evaluation (-1 is ignored)'))

# hyperparmeters for training
parser.add_argument('--num_inner_steps', type=int, default=5,
                    help='number of inner-loop updates')
parser.add_argument('--inner_lr', type=float, default=1e-3,
                    help='inner-loop learning rate initialization')
parser.add_argument('--outer_lr', type=float, default=2e-4,
                    help='outer-loop learning rate')
parser.add_argument('--loss_lr', type=float, default=1e-3,
                    help='outer-loop learning rate')
parser.add_argument('--task_info_lr', type=float, default=1e-3,
                    help='outer-loop learning rate')
parser.add_argument('--num_train_iterations', type=int, default=5000,
                    help='number of outer-loop updates to train for')

# about bert model
parser.add_argument('--seq_len', type=int, default=10,
                    help='sequence length')
parser.add_argument('--bert_num_blocks', type=int, default=2,
                    help='number of bert blocks')
parser.add_argument('--bert_num_heads', type=int, default=4,
                    help='number of attention heads')
parser.add_argument('--bert_hidden_units', type=int, default=128,
                    help='number of hidden units ')
parser.add_argument('--bert_dropout', type=float, default=0.1,
                    help='dropout rate')
parser.add_argument('--model_init_seed', type=int, default=0,
                    help='init seed')

# task generator parameters
parser.add_argument('--num_users', type=int, default=0,
                    help='# of users')
parser.add_argument('--num_items', type=int, default=0,
                    help='number of items')
parser.add_argument('--batch_size', type=int, default=25,
                    help='batch size')
parser.add_argument('--num_users_per_task', type=int, default=2,
                    help='number of users per task')
parser.add_argument('--num_samples', type=int, default=32,
                    help='number of subsamples')

# training options
parser.add_argument('--multi_step_loss_num_epochs', type=int, default=1000,
                    help='number of epochs using multi step loss')
parser.add_argument('--use_multi_step', type=bool, default=True,
                    help='use multi step loss or not')
parser.add_argument('--use_adaptive_loss', type=bool, default=True,
                    help='use adaptive loss or pure maml')

args = parser.parse_args()
