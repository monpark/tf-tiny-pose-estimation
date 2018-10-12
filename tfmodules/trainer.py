# Copyright 2018 Jaewook Kang (jwkang10@gmail.com)
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===================================================================================
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
import time
import sys


from path_manager import TF_MODULE_DIR
from path_manager import EXPORT_DIR
from path_manager import COCO_DATALOAD_DIR
from path_manager import DATASET_DIR


sys.path.insert(0,TF_MODULE_DIR)
sys.path.insert(0,EXPORT_DIR)
sys.path.insert(0,COCO_DATALOAD_DIR)


# < here you need import your module >
from model_config import ModelConfig
from train_config import TrainConfig

from model_builder import ModelBuilder
from data_loader   import DataLoader


def train(dataset_train, dataset_test):
    model_config = ModelConfig()
    train_config = TrainConfig()

    # build dataset ========================

    dataset_handle = tf.placeholder(tf.string, shape=[])
    dataset_train_iterator = dataset_train.make_one_shot_iterator()
    dataset_test_iterator  = dataset_test.make_one_shot_iterator()

    # dataset_train_iterator = dataset_train.make_initializable_iterator()
    # dataset_test_iterator  = dataset_test.make_initializable_iterator()


    dataset_iterator = tf.data.Iterator.from_string_handle(dataset_handle,
                                                           dataset_train.output_types,
                                                           dataset_train.output_shapes)
    inputs, true_heatmap =  dataset_iterator.get_next()

    # model building =========================
    with tf.device('/device:CPU:0'):
        # < complete codes here >
        modelbuilder = ModelBuilder(model_config=model_config)
        pred_heatmap = modelbuilder.get_model(model_in=inputs,
                                              scope='model')

    # traning ops =============================================
        # < complete codes here >
        # batch size에 대한 정규화, batch size 변경 시 비교가 가능하다.
        loss_heatmap        = train_config.loss_fn(true_heatmap - pred_heatmap) / train_config.batch_size
        loss_regularizer    = tf.losses.get_regularization_loss()
        loss_op             = loss_heatmap + loss_regularizer

        global_step = tf.Variable(0, trainable=False)
        batchnum_per_epoch  = np.floor(train_config.train_data_size / train_config.batch_size)


        lr_op = tf.train.exponential_decay(learning_rate=train_config.learning_rate,
                                           global_step=global_step,
                                           decay_steps=train_config.learning_rate_decay_step,
                                           decay_rate=train_config.learning_rate_decay_rate,
                                           staircase=True)

        opt_op      = train_config.opt_fn(learning_rate=lr_op,name='opt_op')
        train_op    = opt_op.minimize(loss_op, global_step)



    # For Tensorboard ===========================================
    # 중간 결과 보려면, tf.summray.image? 같은 함수 사용 가능. 단 서머리가 많아지면 속도가 느려진다.
    file_writer = tf.summary.FileWriter(logdir=train_config.tflogdir)
    file_writer.add_graph(tf.get_default_graph())

    tb_summary_loss_train = tf.summary.scalar('loss_train', loss_op)
    tb_summary_loss_test = tf.summary.scalar('loss_test', loss_op)

    tb_summary_lr   = tf.summary.scalar('learning_rate',lr_op)


    # training ==============================

    init_var = tf.global_variables_initializer()
    print('[train] training_epochs = %s' % train_config.training_epochs)
    print('------------------------------------')

    with tf.Session() as sess:
        # Run the variable initializer
        sess.run(init_var)
        # sess.run(dataset_train_iterator.initializer)
        # sess.run(dataset_test_iterator.initializer)

        train_handle    = sess.run(dataset_train_iterator.string_handle())
        test_handle     = sess.run(dataset_test_iterator.string_handle())

        # for 문이 하나밖에 없다. 나머지 하나는 tf.data에서 처리해준다.
        for epoch in range(train_config.training_epochs):

            train_start_time = time.time()

            # train model
            tf.logging.info('[training sess]')
            _,loss_train = sess.run([train_op,loss_op],
                                     feed_dict={dataset_handle: train_handle,
                                     modelbuilder.dropout_keeprate:model_config.output.dropout_keeprate})


            train_elapsed_time = time.time() - train_start_time

            global_step_eval = global_step.eval()

            if train_config.display_step == 0:
                continue
            elif global_step_eval % train_config.display_step == 0:

                # test model
                tf.logging.info('[test sess]')
                loss_test = loss_op.eval(feed_dict={dataset_handle: test_handle,
                                                    modelbuilder.dropout_keeprate: 1.0})

                # tf summary
                summary_loss_train = tb_summary_loss_train.eval(feed_dict={dataset_handle: train_handle,
                                                                           modelbuilder.dropout_keeprate:1.0})

                summary_loss_test  = tb_summary_loss_test.eval(feed_dict={dataset_handle: test_handle,
                                                                          modelbuilder.dropout_keeprate: 1.0})

                summary_lr         = tb_summary_lr.eval()

                file_writer.add_summary(summary_loss_train,global_step_eval)
                file_writer.add_summary(summary_loss_test,global_step_eval)
                file_writer.add_summary(summary_lr,global_step_eval)

                print('At step = %d, train elapsed_time = %.1f ms' % (global_step_eval, train_elapsed_time))
                print("Training set loss (avg over batch)= %.2f %%  " % (loss_train))
                print("Test set Err loss (total batch)= %.2f %%" % (loss_test))
                print("--------------------------------------------")


        print("Training finished!")

    file_writer.close()


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)


    # dataloader instance gen
    dataloader_train, dataloader_test = \
        [DataLoader(
        is_training     =is_training,
        data_dir        =DATASET_DIR,
        transpose_input =False,
        use_bfloat16    =False) for is_training in [True, False]]

    dataset_train = dataloader_train.input_fn()
    dataset_test  = dataloader_test.input_fn()

    # model tranining
    with tf.name_scope(name='trainer', values=[dataset_train, dataset_test]):
        # < complete the train() function call >
        train(dataset_train=dataset_train,
              dataset_test=dataset_test)