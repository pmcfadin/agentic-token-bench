/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.cassandra.db.compaction;

import java.util.Map;

import org.apache.cassandra.exceptions.ConfigurationException;

/**
 * Tuning parameters for {@link SizeTieredCompactionStrategy}.
 *
 * Controls bucket boundaries and thresholds used by SizeTieredCompactionStrategy
 * to group SSTables for compaction candidate selection.
 */
public final class SizeTieredCompactionStrategyOptions
{
    public static final long DEFAULT_MIN_SSTABLE_SIZE = 50L * 1024L * 1024L;  // 50 MB
    public static final double DEFAULT_BUCKET_LOW = 0.5;
    public static final double DEFAULT_BUCKET_HIGH = 1.5;
    public static final int DEFAULT_MIN_THRESHOLD = 4;
    public static final int DEFAULT_MAX_THRESHOLD = 32;

    public static final String MIN_SSTABLE_SIZE_KEY = "min_sstable_size";
    public static final String BUCKET_LOW_KEY = "bucket_low";
    public static final String BUCKET_HIGH_KEY = "bucket_high";

    public final long minSSTableSize;
    public final double bucketLow;
    public final double bucketHigh;
    public final int minThreshold;
    public final int maxThreshold;

    public SizeTieredCompactionStrategyOptions(Map<String, String> options)
    {
        String v;

        v = options.get(MIN_SSTABLE_SIZE_KEY);
        minSSTableSize = (v == null) ? DEFAULT_MIN_SSTABLE_SIZE : Long.parseLong(v);

        v = options.get(BUCKET_LOW_KEY);
        bucketLow = (v == null) ? DEFAULT_BUCKET_LOW : Double.parseDouble(v);

        v = options.get(BUCKET_HIGH_KEY);
        bucketHigh = (v == null) ? DEFAULT_BUCKET_HIGH : Double.parseDouble(v);

        v = options.get(AbstractCompactionStrategy.MIN_THRESHOLD_KEY);
        minThreshold = (v == null) ? DEFAULT_MIN_THRESHOLD : Integer.parseInt(v);

        v = options.get(AbstractCompactionStrategy.MAX_THRESHOLD_KEY);
        maxThreshold = (v == null) ? DEFAULT_MAX_THRESHOLD : Integer.parseInt(v);
    }

    public static Map<String, String> validateOptions(Map<String, String> options,
                                                       Map<String, String> uncheckedOptions)
        throws ConfigurationException
    {
        String v = options.get(MIN_SSTABLE_SIZE_KEY);
        if (v != null)
        {
            try
            {
                long minSize = Long.parseLong(v);
                if (minSize < 0)
                    throw new ConfigurationException(MIN_SSTABLE_SIZE_KEY + " must be non-negative");
            }
            catch (NumberFormatException e)
            {
                throw new ConfigurationException(MIN_SSTABLE_SIZE_KEY + " is not a valid long value", e);
            }
        }

        v = options.get(BUCKET_LOW_KEY);
        if (v != null)
        {
            double low = Double.parseDouble(v);
            if (low <= 0 || low >= 1)
                throw new ConfigurationException(BUCKET_LOW_KEY + " must be between 0.0 and 1.0 exclusive");
        }

        v = options.get(BUCKET_HIGH_KEY);
        if (v != null)
        {
            double high = Double.parseDouble(v);
            if (high <= 1)
                throw new ConfigurationException(BUCKET_HIGH_KEY + " must be greater than 1.0");
        }

        uncheckedOptions.remove(MIN_SSTABLE_SIZE_KEY);
        uncheckedOptions.remove(BUCKET_LOW_KEY);
        uncheckedOptions.remove(BUCKET_HIGH_KEY);
        return uncheckedOptions;
    }
}
