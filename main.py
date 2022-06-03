from models.bert import BERTModel
from dataloader import DataLoader
from options import args

import torch
import torch.nn as nn
import torch.optim as optim
import copy
import os
import numpy as np
from tqdm import tqdm
from torch.utils.tensorboard import SummaryWriter


SAVE_INTERVAL = 50
LOG_INTERVAL = 1
VAL_INTERVAL = 10
NUM_TEST_TASKS = 100


class MAML:
    def __init__(self, args):

        self.args = args
        self.batch_size = args.batch_size
        self.dataloader = DataLoader(
            file_path=args.data_path, max_sequence_length=args.seq_len, min_sequence=5, samples_per_task=args.num_samples)
        self.args.num_users = self.dataloader.num_users
        self.args.num_items = self.dataloader.num_items

        self.device = torch.device('cpu')
        if torch.cuda.is_available():
            self.device = torch.cuda.current_device()
        # bert4rec model
        self.model = BERTModel(self.args).to(self.device)

        self._log_dir = args.log_dir
        self._save_dir = os.path.join(args.log_dir, 'state')
        os.makedirs(self._log_dir, exist_ok=True)
        os.makedirs(self._save_dir, exist_ok=True)

        # whether to use multi step loss
        self.use_multi_step = args.use_multi_step

        self._num_inner_steps = args.num_inner_steps
        self._inner_lr = args.inner_lr
        self._outer_lr = args.outer_lr

        self.meta_optimizer = optim.SGD(
            self.model.parameters(), lr=self._outer_lr)

        self._train_step = 0

        self.use_adaptive_loss = args.use_adaptive_loss
        # loss function network
        if self.use_adaptive_loss:
            self.loss_network = nn.Sequential(
                nn.Linear(8, 8),
                nn.ReLU(),
                nn.Linear(8, 1),
            ).to(self.device)
            self.loss_lr = 0.01
            self.loss_optimizer = optim.Adam(
                self.loss_network.parameters(), lr=self.loss_lr)

        print("Finished initialization")

    # per step loss weight for multi step loss function

    def get_per_step_loss_importance_vector(self):
        """
        Generates a tensor of dimensionality (num_inner_loop_steps) indicating the importance of each step's target
        loss towards the optimization loss.
        :return: A tensor to be used to compute the weighted average of the loss, useful for
        the MSL (Multi Step Loss) mechanism.
        """
        loss_weights = np.ones(shape=(self._num_inner_steps)) * (
            1.0 / self._num_inner_steps)
        decay_rate = 1.0 / self._num_inner_steps / \
            self.args.multi_step_loss_num_epochs
        min_value_for_non_final_losses = 0.03 / self._num_inner_steps
        for i in range(len(loss_weights) - 1):
            curr_value = np.maximum(
                loss_weights[i] - (self._train_step * decay_rate), min_value_for_non_final_losses)
            loss_weights[i] = curr_value

        curr_value = np.minimum(
            loss_weights[-1] + (self._train_step *
                                (self._num_inner_steps - 1) * decay_rate),
            1.0 - ((self._num_inner_steps - 1) * min_value_for_non_final_losses))
        loss_weights[-1] = curr_value
        loss_weights = torch.Tensor(loss_weights).to(device=self.device)
        return loss_weights

    # update meta paramters
    def update_meta_params(self, query_inputs, query_target_rating, optimizer, loss_fn, mae_loss_fn, phi_model, imp_weight=1):
        # get gradients
        optimizer.zero_grad()
        outputs = phi_model(query_inputs)
        query_loss = loss_fn(outputs, query_target_rating)
        query_loss.backward()

        # update meta loss function
        for k, v in zip(self.model.parameters(), phi_model.parameters()):
            if k.grad == None:
                k.grad = imp_weight*(v.grad)
            else:
                k.grad += imp_weight*(v.grad)
        mae_loss = mae_loss_fn(outputs, query_target_rating)
        return query_loss, mae_loss

    # inner loop optimization

    def _inner_loop(self, support_data, task_info, query_inputs, query_target_rating, imp_vecs, train):
        """Computes the adapted network parameters via the MAML inner loop.

        Args:
            support_data: support data
            task_info: task information
            query_inputs: query data
            query_target_rating: query target
            imp_vecs: important vectors for multi step loss
            train: train params

        Returns:
            query_loss: query mse loss
            mae_loss: query mae loss
        """

        # loss functions
        loss_fn = nn.MSELoss()
        mae_loss_fn = nn.L1Loss()

        # inner loop params
        phi_model = copy.deepcopy(self.model)
        optimizer = optim.SGD(phi_model.parameters(), lr=self._inner_lr)

        # GPU enabling
        user_id, product_history, target_product_id,  product_history_ratings, target_rating = support_data
        inputs = user_id.to(self.device), product_history.to(
            self.device), \
            target_product_id.to(
                self.device),  product_history_ratings.to(self.device)
        task_info = task_info.to(self.device)

        # normalize task information
        task_info_adapt = (task_info-task_info.mean()) / \
            (task_info.std() + 1e-12)
        target_rating = target_rating.to(self.device)

        # inner loop optimization
        for step in range(self._num_inner_steps):
            # update phi(inner loop parameter)
            optimizer.zero_grad()
            outputs = phi_model(inputs)
            loss = loss_fn(outputs, target_rating)
            if self.use_adaptive_loss:
                loss += self.loss_network(task_info_adapt)[0]
            loss.backward()
            optimizer.step()

            ##### multi step loss ######
            if self.use_multi_step and self._train_step < self.args.multi_step_loss_num_epochs and train:
                query_loss, mae_loss = self.update_meta_params(
                    query_inputs, query_target_rating, optimizer, loss_fn, mae_loss_fn, phi_model, imp_vecs[step])

            # Fo-maml loss
            else:
                # after all updates
                if step == self._num_inner_steps - 1:
                    if train:
                        phi_model.train()
                    else:
                        phi_model.eval()

                    query_loss, mae_loss = self.update_meta_params(
                        query_inputs, query_target_rating, optimizer, loss_fn, mae_loss_fn, phi_model)

        return query_loss, mae_loss

    # outer loop

    def _outer_loop(self, task_batch, train=None):
        """Computes the MAML loss and metrics on a batch of tasks.

        Args:
            task_batch (tuple): batch of tasks from an Omniglot DataLoader
            train (bool): whether we are training or evaluating

        Returns:
            outer_loss: mean query MSE loss over the batch
            mae_loss: mean query MAE loss over the batch
        """
        # get importance weight
        imp_vecs = self.get_per_step_loss_importance_vector()

        outer_loss_batch = []
        mae_loss_batch = []

        self.meta_optimizer.zero_grad()
        if self.use_adaptive_loss:
            self.loss_optimizer.zero_grad()

        # loop through task batch
        for idx, task in enumerate(tqdm(task_batch)):
            # query data -> move them to gpu
            support, query, task_info = task
            user_id, product_history, target_product_id,  product_history_ratings, target_rating = query
            query_inputs = user_id.to(self.device), product_history.to(
                self.device), \
                target_product_id.to(
                    self.device),  product_history_ratings.to(self.device)
            query_target_rating = target_rating.to(self.device)

            # inner loop operation
            loss, mae_loss = self._inner_loop(
                support, task_info, query_inputs, query_target_rating, imp_vecs, train)  # do inner loop

            mae_loss_batch.append(mae_loss.detach().to("cpu").item())
            outer_loss_batch.append(loss.detach().to("cpu").item())

        # Update meta parameters
        if train:
            self.meta_optimizer.step()
            if self.use_adaptive_loss:
                self.loss_optimizer.step()

        outer_loss = np.mean(outer_loss_batch)
        mae_loss = np.mean(mae_loss_batch)

        return outer_loss, mae_loss

    def train(self, train_steps):
        """Train the MAML.

        Optimizes MAML meta-parameters
        while periodically validating on validation_tasks, logging metrics, and
        saving checkpoints.

        Args:
            train_steps (int) : the number of steps this model should train for
        """
        print(f"Starting MAML training at iteration {self._train_step}")
        writer = SummaryWriter(log_dir=self._log_dir)
        val_batches = self.dataloader.generate_task(
            mode="valid", batch_size=50)
        for i in range(1, train_steps+1):
            self._train_step += 1
            train_task = self.dataloader.generate_task(
                mode="train", batch_size=self.batch_size)

            outer_loss, mae_loss = self._outer_loop(
                train_task, train=True)

            if self._train_step % SAVE_INTERVAL == 0:
                self._save_model()

            if i % LOG_INTERVAL == 0:
                print(
                    f'Iteration {self._train_step}: '
                    f'MSE loss: {outer_loss:.3f} | '
                    f'MAE loss: {mae_loss:.3f} | '
                )
                writer.add_scalar(
                    "train/MSEloss", outer_loss, self._train_step)
                writer.add_scalar("train/MAEloss", mae_loss, self._train_step)

            if i % VAL_INTERVAL == 0:
                outer_loss, mae_loss = self._outer_loop(
                    val_batches, train=False)

                print(
                    f'\t-Validation: '
                    f'Val MSE loss: {outer_loss:.3f} | '
                    f'Val MAE loss: {mae_loss:.3f} | '
                )

                writer.add_scalar(
                    "valid/MSEloss", outer_loss, self._train_step)
                writer.add_scalar("valid/MAEloss", mae_loss, self._train_step)
        writer.close()

    def test(self):
        accuracies = []
        test = [self.val_data.generate_task(
            NUM_TEST_TASKS//10) for _ in range(10)]
        for test_data in test:
            if self.is_plus:
                _, _, accuracy_query = self._outer_loop_plus(
                    test_data, train=False)
            else:
                _, _, accuracy_query = self._outer_loop(test_data, train=False)
            accuracies.append(accuracy_query)
        mean = np.mean(accuracies)
        std = np.std(accuracies)
        mean_95_confidence_interval = 1.96 * std / np.sqrt(10)
        print(
            f'Accuracy over {NUM_TEST_TASKS} test tasks: '
            f'mean {mean:.3f}, '
            f'95% confidence interval {mean_95_confidence_interval:.3f}'
        )

    def load(self, checkpoint_step):
        target_path = os.path.join(self._save_dir, f"{checkpoint_step}")
        print("Loading checkpoint from", target_path)
        try:
            self.model.load_state_dict(torch.load(target_path))

        except:
            raise ValueError(
                f'No checkpoint for iteration {checkpoint_step} found.')

    def _save_model(self):
        # Save a model to 'save_dir'
        torch.save(self.model.state_dict(),
                   os.path.join(self._save_dir, f"{self._train_step}"))


def main(args):
    if args.log_dir is None:
        args.log_dir = os.path.join(os.path.abspath('.'), "p1_log/")

    print(f'log_dir: {args.log_dir}')

    maml = MAML(
        args
    )

    if args.checkpoint_step > -1:
        maml.load(args.checkpoint_step)
    else:
        print('Checkpoint loading skipped.')

    if not args.test:
        maml.train(args.num_train_iterations)

    else:
        maml.test()


if __name__ == '__main__':
    main(args)
