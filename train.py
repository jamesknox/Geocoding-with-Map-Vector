# -*- coding: utf-8 -*-
import codecs
import numpy as np
import cPickle
from keras import Input
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.engine import Model
from keras.layers.merge import concatenate
from keras.layers import Embedding, Dense, LSTM, Dropout, Conv1D, GlobalMaxPooling1D
from preprocessing import generate_arrays_from_file, GRID_SIZE, BATCH_SIZE, EMB_DIM, CONTEXT_LENGTH, UNKNOWN, PADDING
from subprocess import check_output

print(u"Dimension:", EMB_DIM)
print(u"Input length:", CONTEXT_LENGTH)

words = cPickle.load(open(u"data/vocab_words.pkl"))
locations = cPickle.load(open(u"data/vocab_locations.pkl"))
vocabulary = words.union(locations)
print(u"Vocabulary Size:", len(vocabulary))
#  --------------------------------------------------------------------------------------------------------------------
print(u'Preparing vectors...')
word_to_index = dict([(w, i) for i, w in enumerate(vocabulary)])

vectors = {UNKNOWN: np.ones(EMB_DIM), PADDING: np.ones(EMB_DIM)}
for line in codecs.open(u"../data/glove.twitter." + str(EMB_DIM) + u"d.txt", encoding=u"utf-8"):
    if line.strip() == "":
        continue
    t = line.split()
    vectors[t[0]] = [float(x) for x in t[1:]]
print(u'Loaded Twitter vectors...', len(vectors))

for line in codecs.open(u"../data/glove." + str(EMB_DIM) + u"d.txt", encoding=u"utf-8"):
    if line.strip() == u"":
        continue
    t = line.split()
    vectors[t[0]] = [float(x) for x in t[1:]]
print(u'Loaded GloVe vectors...', len(vectors))

weights = np.zeros((len(vocabulary), EMB_DIM))
oov = 0
for w in vocabulary:
    if w in vectors:
        weights[word_to_index[w]] = vectors[w]
    else:
        weights[word_to_index[w]] = np.random.normal(size=(EMB_DIM,), scale=0.3)
        oov += 1

weights = np.array([weights])
print(u'Done preparing vectors...')
print(u"OOV (no vectors):", oov)
#  --------------------------------------------------------------------------------------------------------------------
print(u'Building model...')
left_words = Input(shape=(CONTEXT_LENGTH,))
lw = Embedding(len(vocabulary), EMB_DIM, input_length=CONTEXT_LENGTH, weights=weights)(left_words)
lw = Conv1D(500, 2, activation='relu', strides=1)(lw)
lw = GlobalMaxPooling1D()(lw)
lw = Dense(200)(lw)
lw = Dropout(0.3)(lw)

right_words = Input(shape=(CONTEXT_LENGTH,))
rw = Embedding(len(vocabulary), EMB_DIM, input_length=CONTEXT_LENGTH, weights=weights)(right_words)
rw = Conv1D(500, 2, activation='relu', strides=1)(rw)
rw = GlobalMaxPooling1D()(rw)
rw = Dense(200)(rw)
rw = Dropout(0.3)(rw)

entities_strings_left = Input(shape=(CONTEXT_LENGTH,))
esl = Embedding(len(vocabulary), EMB_DIM, input_length=CONTEXT_LENGTH, weights=weights)(entities_strings_left)
esl = Conv1D(500, 2, activation='relu', strides=1)(esl)
esl = GlobalMaxPooling1D()(esl)
esl = Dense(200)(esl)
esl = Dropout(0.3)(esl)

entities_strings_right = Input(shape=(CONTEXT_LENGTH,))
esr = Embedding(len(vocabulary), EMB_DIM, input_length=CONTEXT_LENGTH, weights=weights)(entities_strings_right)
esr = Conv1D(500, 2, activation='relu', strides=1)(esr)
esr = GlobalMaxPooling1D()(esr)
esr = Dense(200)(esr)
esr = Dropout(0.3)(esr)

entities_coord_left = Input(shape=((180 / GRID_SIZE) * (360 / GRID_SIZE),))
ecl = Dense(200, activation='relu', input_dim=(180 / GRID_SIZE) * (360 / GRID_SIZE))(entities_coord_left)
ecl = Dropout(0.3)(ecl)

entities_coord_right = Input(shape=((180 / GRID_SIZE) * (360 / GRID_SIZE),))
ecr = Dense(200, activation='relu', input_dim=(180 / GRID_SIZE) * (360 / GRID_SIZE))(entities_coord_right)
ecr = Dropout(0.3)(ecr)

target_coord = Input(shape=((180 / GRID_SIZE) * (360 / GRID_SIZE),))
tc = Dense(500, activation='relu', input_dim=(180 / GRID_SIZE) * (360 / GRID_SIZE))(target_coord)
tc = Dropout(0.3)(tc)

target_string = Input(shape=(15,))
ts = Embedding(len(vocabulary), EMB_DIM, input_length=15, weights=weights)(target_string)
ts = Conv1D(500, 2, activation='relu', strides=1)(ts)
ts = GlobalMaxPooling1D()(ts)
ts = Dense(500)(ts)
ts = Dropout(0.3)(ts)

inp = concatenate([lw, rw, esl, esr, ecl, ecr, tc, ts])
inp = Dense(units=(180 / GRID_SIZE) * (360 / GRID_SIZE), activation='softmax')(inp)
model = Model(inputs=[left_words, right_words, entities_strings_left, entities_strings_right,
                      entities_coord_left, entities_coord_right, target_coord, target_string], outputs=[inp])
model.compile(loss='categorical_crossentropy', optimizer='rmsprop', metrics=['accuracy'])

print(u'Finished building model...')
#  --------------------------------------------------------------------------------------------------------------------
checkpoint = ModelCheckpoint(filepath="../data/weights", verbose=0)
# checkpoint = ModelCheckpoint(filepath="../data/weights.{epoch:02d}-{acc:.2f}.hdf5", verbose=0)
early_stop = EarlyStopping(monitor='acc', patience=5)
file_name = u"data/eval_lgl.txt"
model.fit_generator(generate_arrays_from_file(file_name, word_to_index),
                    steps_per_epoch=int(check_output(["wc", file_name]).split()[0]) / BATCH_SIZE,
                    epochs=100, callbacks=[checkpoint, early_stop])
